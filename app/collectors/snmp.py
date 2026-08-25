from __future__ import annotations

import asyncio
import ipaddress
import random
import re
import socket
import time
from dataclasses import dataclass
from typing import Any, Iterable


QNAP_ROOT = "1.3.6.1.4.1.55062.1"
QNAP_STORAGE = f"{QNAP_ROOT}.10"
QNAP_SYSTEM = f"{QNAP_ROOT}.12"
QNAP_EXTERNAL = f"{QNAP_ROOT}.13"


def _encode_length(length: int) -> bytes:
    if length < 128:
        return bytes((length,))
    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes((0x80 | len(raw),)) + raw


def _tlv(tag: int, value: bytes) -> bytes:
    return bytes((tag,)) + _encode_length(len(value)) + value


def _integer(value: int) -> bytes:
    if value == 0:
        raw = b"\x00"
    else:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big", signed=False)
        if raw[0] & 0x80:
            raw = b"\x00" + raw
    return _tlv(0x02, raw)


def _oid(value: str) -> bytes:
    parts = [int(part) for part in value.strip(".").split(".")]
    if len(parts) < 2:
        raise ValueError("OID requires at least two components")
    encoded = bytearray((parts[0] * 40 + parts[1],))
    for part in parts[2:]:
        stack = [part & 0x7F]
        part >>= 7
        while part:
            stack.append(0x80 | (part & 0x7F))
            part >>= 7
        encoded.extend(reversed(stack))
    return _tlv(0x06, bytes(encoded))


def _read_tlv(data: bytes, offset: int = 0) -> tuple[int, bytes, int]:
    if offset + 2 > len(data):
        raise ValueError("Truncated BER value")
    tag = data[offset]
    first_length = data[offset + 1]
    offset += 2
    if first_length & 0x80:
        count = first_length & 0x7F
        if not count or offset + count > len(data):
            raise ValueError("Invalid BER length")
        length = int.from_bytes(data[offset : offset + count], "big")
        offset += count
    else:
        length = first_length
    end = offset + length
    if end > len(data):
        raise ValueError("Truncated BER payload")
    return tag, data[offset:end], end


def _decode_number(tag: int, value: bytes) -> float | str:
    if tag == 0x02:
        return float(int.from_bytes(value, "big", signed=bool(value and value[0] & 0x80)))
    if tag in {0x41, 0x42, 0x43, 0x46}:
        return float(int.from_bytes(value, "big", signed=False))
    if tag == 0x04:
        return value.decode("utf-8", errors="replace")
    if tag in {0x80, 0x81, 0x82}:
        raise ValueError("SNMP exception value")
    raise ValueError(f"Unsupported SNMP value tag 0x{tag:02x}")


@dataclass(frozen=True, slots=True)
class SnmpMetric:
    name: str
    oid: str
    kind: str = "gauge"
    unit: str = ""


class SnmpQueryError(RuntimeError):
    """An SNMP operation failed without carrying credentials into the error."""


class PysnmpSession:
    """Small PySNMP adapter used for SNMPv3 and table operations."""

    def __init__(
        self,
        version: str,
        community: str,
        username: str,
        auth_protocol: str,
        auth_password: str,
        priv_protocol: str,
        priv_password: str,
        timeout: float,
    ) -> None:
        self.version = version
        self.community = community
        self.username = username
        self.auth_protocol = auth_protocol.upper().replace("HMAC-", "")
        self.auth_password = auth_password
        self.priv_protocol = priv_protocol.upper().replace("CBC-", "")
        self.priv_password = priv_password
        self.timeout = timeout
        self._validate_security()

    def _validate_security(self) -> None:
        if self.version not in {"2c", "3"}:
            raise ValueError("SNMP_VERSION must be 2c or 3")
        if self.version == "3":
            if not self.username or not self.auth_password or not self.priv_password:
                raise ValueError("SNMPv3 authPriv requires username, authentication password and privacy password")
            if not 8 <= len(self.auth_password.encode("utf-8")) <= 32:
                raise ValueError("SNMPv3 authentication password must be 8 to 32 bytes")
            if not 8 <= len(self.priv_password.encode("utf-8")) <= 32:
                raise ValueError("SNMPv3 privacy password must be 8 to 32 bytes")
            if self.auth_protocol not in {"MD5", "SHA", "SHA1"}:
                raise ValueError("SNMP_AUTH_PROTOCOL must be MD5 or SHA")
            if self.priv_protocol not in {"DES", "AES", "AES128"}:
                raise ValueError("SNMP_PRIV_PROTOCOL must be DES or AES")

    async def query(
        self,
        target: str,
        scalar_oids: Iterable[str],
        table_index_oids: Iterable[str],
        table_columns: dict[str, tuple[str, ...]],
    ) -> tuple[dict[str, Any], dict[str, tuple[str, ...]], list[dict[str, str]]]:
        try:
            from pysnmp.hlapi.v3arch.asyncio import (
                CommunityData,
                ContextData,
                ObjectIdentity,
                ObjectType,
                SnmpEngine,
                UdpTransportTarget,
                USM_AUTH_HMAC96_MD5,
                USM_AUTH_HMAC96_SHA,
                USM_PRIV_CBC56_DES,
                USM_PRIV_CFB128_AES,
                UsmUserData,
                get_cmd,
                walk_cmd,
            )
        except ImportError as exc:
            raise RuntimeError("PySNMP is required for SNMPv3 and QNAP table collection") from exc

        engine = SnmpEngine()
        errors: list[dict[str, str]] = []
        try:
            transport = await UdpTransportTarget.create((target, 161), timeout=self.timeout, retries=0)
            if self.version == "3":
                auth = UsmUserData(
                    self.username,
                    authKey=self.auth_password,
                    privKey=self.priv_password,
                    authProtocol=USM_AUTH_HMAC96_MD5 if self.auth_protocol == "MD5" else USM_AUTH_HMAC96_SHA,
                    privProtocol=USM_PRIV_CBC56_DES if self.priv_protocol == "DES" else USM_PRIV_CFB128_AES,
                )
            else:
                auth = CommunityData(self.community, mpModel=1)
            context = ContextData()

            async def get_many(oids: Iterable[str]) -> dict[str, Any]:
                result: dict[str, Any] = {}
                requested = tuple(dict.fromkeys(oids))
                for offset in range(0, len(requested), 40):
                    chunk = requested[offset : offset + 40]
                    response = await get_cmd(
                        engine,
                        auth,
                        transport,
                        context,
                        *(ObjectType(ObjectIdentity(oid)) for oid in chunk),
                        lookupMib=False,
                    )
                    error_indication, error_status, _, var_binds = response
                    if error_indication:
                        raise SnmpQueryError("SNMP GET failed")
                    if error_status:
                        # Some QNAP firmware returns a PDU error instead of a
                        # per-variable exception for unsupported optional OIDs.
                        # Retry the members separately so one absent feature
                        # (for example an unavailable UPS) cannot discard CPU
                        # and storage telemetry from the same request.
                        if len(chunk) > 1:
                            for oid in chunk:
                                try:
                                    result.update(await get_many((oid,)))
                                except SnmpQueryError:
                                    errors.append({"target": target, "metric": oid, "error": "SnmpQueryError"})
                            continue
                        raise SnmpQueryError("SNMP GET failed")
                    for var_bind in var_binds:
                        oid, value = var_bind
                        decoded = _decode_pysnmp_value(value)
                        if decoded is not None:
                            result[oid.prettyPrint().lstrip(".")] = decoded
                return result

            scalars: dict[str, Any] = {}
            # QTS can silently drop requests for optional scalar objects that
            # are not implemented on a particular model. Query the small
            # identity set independently so those omissions do not block the
            # storage tables that the NAS does expose.
            for oid in scalar_oids:
                try:
                    scalars.update(await get_many((oid,)))
                except SnmpQueryError:
                    errors.append({"target": target, "metric": oid, "error": "SnmpQueryError"})
            indices: dict[str, tuple[str, ...]] = {}
            for base_oid in table_index_oids:
                found: list[str] = []
                try:
                    iterator = walk_cmd(
                        engine,
                        auth,
                        transport,
                        context,
                        ObjectType(ObjectIdentity(base_oid)),
                        lexicographicMode=False,
                        lookupMib=False,
                    )
                    async for error_indication, error_status, _, var_binds in iterator:
                        if error_indication or error_status:
                            raise SnmpQueryError("SNMP WALK failed")
                        for var_bind in var_binds:
                            returned_oid = var_bind[0].prettyPrint().lstrip(".")
                            prefix = f"{base_oid}."
                            if returned_oid.startswith(prefix):
                                suffix = returned_oid[len(prefix) :]
                                if suffix and suffix not in found:
                                    found.append(suffix)
                        if len(found) >= 64:
                            break
                except SnmpQueryError:
                    errors.append({"target": target, "metric": base_oid, "error": "SnmpQueryError"})
                indices[base_oid] = tuple(found)

            cells: dict[str, tuple[str, ...]] = {}
            requested_cells: list[str] = []
            for index_oid, columns in table_columns.items():
                for index in indices.get(index_oid, ()):
                    for column in columns:
                        requested_cells.append(f"{column}.{index}")
            if requested_cells:
                try:
                    cell_values = await get_many(requested_cells)
                except SnmpQueryError:
                    errors.append({"target": target, "metric": "qnap_tables", "error": "SnmpQueryError"})
                    cell_values = {}
                for oid, value in cell_values.items():
                    cells[oid] = (str(value),)
            return scalars | {oid: values[0] for oid, values in cells.items()}, indices, errors
        finally:
            engine.close_dispatcher()


def _decode_pysnmp_value(value: Any) -> int | float | str | None:
    class_name = value.__class__.__name__
    if class_name in {"NoSuchObject", "NoSuchInstance", "EndOfMibView", "Null"}:
        return None
    if class_name in {
        "Integer", "Integer32", "Counter", "Counter32", "Counter64", "Gauge", "Gauge32", "Unsigned32", "TimeTicks",
    }:
        return int(value)
    return value.prettyPrint().strip()


class SnmpCollector:
    """Read-only SNMP collector with legacy v2c and QNAP SNMPv3 profiles."""

    def __init__(
        self,
        targets: Iterable[str],
        community: str,
        interface_index: int = 2,
        extra_oids: Iterable[str] = (),
        *,
        version: str = "2c",
        username: str = "",
        auth_protocol: str = "SHA",
        auth_password: str = "",
        priv_protocol: str = "DES",
        priv_password: str = "",
        profile: str = "generic",
        timeout: float = 2.0,
    ) -> None:
        self.targets = tuple(dict.fromkeys(targets))
        self.community_text = community
        self.community = community.encode("utf-8")
        self.version = version.strip().lower()
        self.username = username
        self.auth_protocol = auth_protocol
        self.auth_password = auth_password
        self.priv_protocol = priv_protocol
        self.priv_password = priv_password
        self.profile = profile.strip().lower()
        self.timeout = max(0.5, float(timeout))
        index = max(1, int(interface_index))
        metrics = [
            SnmpMetric("system_uptime", "1.3.6.1.2.1.1.3.0", "gauge", "ticks"),
            SnmpMetric("wan_rx_total", f"1.3.6.1.2.1.31.1.1.1.6.{index}", "counter", "bytes"),
            SnmpMetric("wan_tx_total", f"1.3.6.1.2.1.31.1.1.1.10.{index}", "counter", "bytes"),
        ]
        for item in extra_oids:
            name, separator, oid = item.partition("=")
            if separator and name.strip() and oid.strip():
                metrics.append(SnmpMetric(name.strip(), oid.strip(), "gauge", ""))
        self.metrics = tuple(metrics)
        self._previous: dict[tuple[str, str], tuple[float, float]] = {}
        self.last_details: list[dict[str, Any]] = []

    def collect(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        if self.profile == "qnap":
            return self._collect_qnap()
        if self.version == "3":
            return self._collect_pysnmp_generic()
        return self._collect_legacy_v2c()

    def _collect_legacy_v2c(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        samples: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        now = time.time()
        self.last_details = []
        for target in self.targets:
            if not _is_local_target(target):
                errors.append({"target": target, "metric": "target", "error": "NonLocalTarget"})
                continue
            for metric in self.metrics:
                try:
                    raw_value = self._get(target, metric.oid)
                    if not isinstance(raw_value, float):
                        continue
                    samples.extend(self._metric_samples(now, target, metric, raw_value))
                except (OSError, TimeoutError, ValueError) as exc:
                    errors.append({"target": target, "metric": metric.name, "error": type(exc).__name__})
        return samples, errors

    def _collect_pysnmp_generic(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        samples: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        now = time.time()
        self.last_details = []
        for target in self.targets:
            if not _is_local_target(target):
                errors.append({"target": target, "metric": "target", "error": "NonLocalTarget"})
                continue
            try:
                values, _, query_errors = asyncio.run(
                    self._session().query(target, (item.oid for item in self.metrics), (), {})
                )
                errors.extend(query_errors)
                for metric in self.metrics:
                    raw_value = values.get(metric.oid)
                    if isinstance(raw_value, (int, float)):
                        samples.extend(self._metric_samples(now, target, metric, float(raw_value)))
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append({"target": target, "metric": "snmp", "error": type(exc).__name__})
        return samples, errors

    def _collect_qnap(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        samples: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        details: list[dict[str, Any]] = []
        now = time.time()
        for target in self.targets:
            if not _is_local_target(target):
                errors.append({"target": target, "metric": "target", "error": "NonLocalTarget"})
                continue
            try:
                values, indices, query_errors = asyncio.run(
                    self._session().query(target, _qnap_scalar_oids(), _qnap_index_oids(), _qnap_table_columns())
                )
                errors.extend(query_errors)
                detail, target_samples = _build_qnap_snapshot(target, values, indices, now)
                details.append(detail)
                samples.extend(target_samples)
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append({"target": target, "metric": "qnap", "error": type(exc).__name__})
        self.last_details = details
        return samples, errors

    def _session(self) -> PysnmpSession:
        return PysnmpSession(
            self.version,
            self.community_text,
            self.username,
            self.auth_protocol,
            self.auth_password,
            self.priv_protocol,
            self.priv_password,
            self.timeout,
        )

    def _metric_samples(self, now: float, target: str, metric: SnmpMetric, raw_value: float) -> list[dict[str, Any]]:
        samples = [{"ts": now, "target": target, "metric": metric.name, "value": raw_value, "unit": metric.unit}]
        if metric.kind == "counter":
            key = (target, metric.name)
            previous = self._previous.get(key)
            if previous and raw_value >= previous[1]:
                elapsed = max(0.001, now - previous[0])
                samples.append(
                    {
                        "ts": now,
                        "target": target,
                        "metric": metric.name.removesuffix("_total") + "_bps",
                        "value": (raw_value - previous[1]) / elapsed,
                        "unit": "bytes/s",
                    }
                )
            self._previous[key] = (now, raw_value)
        return samples

    def _get(self, target: str, oid: str) -> float | str:
        request_id = random.randint(1, 2_000_000_000)
        varbind = _tlv(0x30, _oid(oid) + _tlv(0x05, b""))
        varbinds = _tlv(0x30, varbind)
        pdu = _tlv(0xA0, _integer(request_id) + _integer(0) + _integer(0) + varbinds)
        message = _tlv(0x30, _integer(1) + _tlv(0x04, self.community) + pdu)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.sendto(message, (target, 161))
            response, _ = sock.recvfrom(65535)
        return self._parse_response(response, request_id)

    def _parse_response(self, data: bytes, request_id: int) -> float | str:
        root_tag, root, _ = _read_tlv(data)
        if root_tag != 0x30:
            raise ValueError("Invalid SNMP message")
        _, _, offset = _read_tlv(root, 0)
        _, _, offset = _read_tlv(root, offset)
        pdu_tag, pdu, _ = _read_tlv(root, offset)
        if pdu_tag != 0xA2:
            raise ValueError("Not an SNMP response")
        _, request_raw, offset = _read_tlv(pdu, 0)
        if int.from_bytes(request_raw, "big", signed=False) != request_id:
            raise ValueError("Mismatched SNMP request ID")
        _, error_raw, offset = _read_tlv(pdu, offset)
        if int.from_bytes(error_raw, "big", signed=False) != 0:
            raise ValueError("SNMP agent returned an error")
        _, _, offset = _read_tlv(pdu, offset)
        _, varbinds, _ = _read_tlv(pdu, offset)
        _, varbind, _ = _read_tlv(varbinds, 0)
        _, _, value_offset = _read_tlv(varbind, 0)
        value_tag, value_raw, _ = _read_tlv(varbind, value_offset)
        return _decode_number(value_tag, value_raw)


def _is_local_target(target: str) -> bool:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(target, 161, type=socket.SOCK_DGRAM)}
    except socket.gaierror:
        return False
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        if not (ip.is_private or ip.is_loopback or ip.is_link_local):
            return False
    return bool(addresses)


def _qnap_scalar_oids() -> tuple[str, ...]:
    # Every scalar that _build_qnap_snapshot reads. PysnmpSession.query fetches
    # the identity objects one by one, so an OID absent on a given model
    # (reported as noSuchInstance or a per-variable PDU error) is skipped
    # without discarding the remaining system health values.
    return (
        # Identity
        f"{QNAP_SYSTEM}.3.0",
        f"{QNAP_SYSTEM}.4.0",
        f"{QNAP_SYSTEM}.6.0",
        # System health
        f"{QNAP_SYSTEM}.10.0",
        f"{QNAP_SYSTEM}.11.0",
        f"{QNAP_SYSTEM}.12.0",
        f"{QNAP_SYSTEM}.13.0",
        f"{QNAP_SYSTEM}.14.0",
        f"{QNAP_SYSTEM}.15.0",
        f"{QNAP_SYSTEM}.16.0",
        f"{QNAP_SYSTEM}.19.0",
        f"{QNAP_SYSTEM}.20.0",
        f"{QNAP_SYSTEM}.21.0",
        # SSD cache
        f"{QNAP_STORAGE}.10.0",
        f"{QNAP_STORAGE}.11.0",
        f"{QNAP_STORAGE}.12.0",
        f"{QNAP_STORAGE}.13.0",
        f"{QNAP_STORAGE}.14.0",
        # UPS
        f"{QNAP_EXTERNAL}.1.0",
        f"{QNAP_EXTERNAL}.6.0",
        f"{QNAP_EXTERNAL}.7.0",
    )


def _qnap_index_oids() -> tuple[str, ...]:
    return (
        f"{QNAP_SYSTEM}.9.1.1",
        f"{QNAP_STORAGE}.2.1.1",
        f"{QNAP_STORAGE}.5.1.1",
        f"{QNAP_STORAGE}.7.1.1",
        f"{QNAP_STORAGE}.9.1.1",
    )


def _qnap_table_columns() -> dict[str, tuple[str, ...]]:
    return {
        f"{QNAP_SYSTEM}.9.1.1": (f"{QNAP_SYSTEM}.9.1.2", f"{QNAP_SYSTEM}.9.1.3"),
        f"{QNAP_STORAGE}.2.1.1": (
            f"{QNAP_STORAGE}.2.1.2", f"{QNAP_STORAGE}.2.1.3", f"{QNAP_STORAGE}.2.1.4",
            f"{QNAP_STORAGE}.2.1.6", f"{QNAP_STORAGE}.2.1.7", f"{QNAP_STORAGE}.2.1.8",
            f"{QNAP_STORAGE}.2.1.9",
        ),
        f"{QNAP_STORAGE}.5.1.1": (
            f"{QNAP_STORAGE}.5.1.2", f"{QNAP_STORAGE}.5.1.3", f"{QNAP_STORAGE}.5.1.4",
            f"{QNAP_STORAGE}.5.1.5", f"{QNAP_STORAGE}.5.1.7",
        ),
        f"{QNAP_STORAGE}.7.1.1": (
            f"{QNAP_STORAGE}.7.1.2", f"{QNAP_STORAGE}.7.1.3", f"{QNAP_STORAGE}.7.1.4",
            f"{QNAP_STORAGE}.7.1.5",
        ),
        f"{QNAP_STORAGE}.9.1.1": (
            f"{QNAP_STORAGE}.9.1.2", f"{QNAP_STORAGE}.9.1.3", f"{QNAP_STORAGE}.9.1.4",
            f"{QNAP_STORAGE}.9.1.5", f"{QNAP_STORAGE}.9.1.6", f"{QNAP_STORAGE}.9.1.7",
            f"{QNAP_STORAGE}.9.1.8",
        ),
    }


def _build_qnap_snapshot(
    target: str, values: dict[str, Any], indices: dict[str, tuple[str, ...]], now: float
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    def value(oid: str, default: Any = None) -> Any:
        return values.get(oid, default)

    def rows(index_oid: str, fields: dict[str, str]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for index in indices.get(index_oid, ()):
            row = {"index": index}
            for name, column in fields.items():
                row[name] = value(f"{column}.{index}")
            result.append(row)
        return result

    fans = rows(
        f"{QNAP_SYSTEM}.9.1.1",
        {"id": f"{QNAP_SYSTEM}.9.1.2", "speed_rpm": f"{QNAP_SYSTEM}.9.1.3"},
    )
    disks = rows(
        f"{QNAP_STORAGE}.2.1.1",
        {
            "id": f"{QNAP_STORAGE}.2.1.2", "manufacturer": f"{QNAP_STORAGE}.2.1.3",
            "model": f"{QNAP_STORAGE}.2.1.4", "type": f"{QNAP_STORAGE}.2.1.6",
            "status": f"{QNAP_STORAGE}.2.1.7", "temperature_celsius": f"{QNAP_STORAGE}.2.1.8",
            "capacity_bytes": f"{QNAP_STORAGE}.2.1.9",
        },
    )
    raids = rows(
        f"{QNAP_STORAGE}.5.1.1",
        {
            "id": f"{QNAP_STORAGE}.5.1.2", "name": f"{QNAP_STORAGE}.5.1.3",
            "status": f"{QNAP_STORAGE}.5.1.4", "capacity_bytes": f"{QNAP_STORAGE}.5.1.5",
            "level": f"{QNAP_STORAGE}.5.1.7",
        },
    )
    pools = rows(
        f"{QNAP_STORAGE}.7.1.1",
        {
            "id": f"{QNAP_STORAGE}.7.1.2", "capacity_bytes": f"{QNAP_STORAGE}.7.1.3",
            "free_bytes": f"{QNAP_STORAGE}.7.1.4", "status": f"{QNAP_STORAGE}.7.1.5",
        },
    )
    volumes = rows(
        f"{QNAP_STORAGE}.9.1.1",
        {
            "id": f"{QNAP_STORAGE}.9.1.2", "capacity_bytes": f"{QNAP_STORAGE}.9.1.3",
            "free_bytes": f"{QNAP_STORAGE}.9.1.4", "status": f"{QNAP_STORAGE}.9.1.5",
            "ssd_cache_enabled": f"{QNAP_STORAGE}.9.1.6", "thin_provisioned": f"{QNAP_STORAGE}.9.1.7",
            "name": f"{QNAP_STORAGE}.9.1.8",
        },
    )

    power_raw = _as_int(value(f"{QNAP_SYSTEM}.19.0"))
    pool_status = {-3: "error", -2: "not_ready", -1: "warning", 0: "ready"}
    for pool in pools:
        raw = _as_int(pool.get("status"))
        pool["status_code"] = raw
        pool["status"] = pool_status.get(raw, f"unknown_{raw}" if raw is not None else "unknown")

    uptime_ticks = _as_number(value(f"{QNAP_SYSTEM}.21.0"))
    system = {
        "cpu_percent": _as_number(value(f"{QNAP_SYSTEM}.12.0")),
        "cpu_temperature_celsius": _as_number(value(f"{QNAP_SYSTEM}.10.0")),
        "system_temperature_celsius": _as_number(value(f"{QNAP_SYSTEM}.11.0")),
        "memory_total_bytes": _as_number(value(f"{QNAP_SYSTEM}.13.0")),
        "memory_free_bytes": _as_number(value(f"{QNAP_SYSTEM}.14.0")),
        "memory_available_bytes": _as_number(value(f"{QNAP_SYSTEM}.15.0")),
        "memory_used_bytes": _as_number(value(f"{QNAP_SYSTEM}.16.0")),
        "power_status": "ok" if power_raw == 0 else ("failed" if power_raw == -1 else "unknown"),
        "ups_status_code": _as_int(value(f"{QNAP_SYSTEM}.20.0")),
        "uptime_seconds": uptime_ticks / 100 if uptime_ticks is not None else None,
        "fans": fans,
    }
    cache = {
        "enabled": _as_int(value(f"{QNAP_STORAGE}.10.0")) == 1,
        "available_percent": _as_number(value(f"{QNAP_STORAGE}.11.0")),
        "read_hit_percent": _as_number(value(f"{QNAP_STORAGE}.12.0")),
        "write_hit_percent": _as_number(value(f"{QNAP_STORAGE}.13.0")),
        "status_code": _as_int(value(f"{QNAP_STORAGE}.14.0")),
    }
    ups = {
        "status": value(f"{QNAP_EXTERNAL}.1.0"),
        "load_percent": _as_number(value(f"{QNAP_EXTERNAL}.6.0")),
        "battery_percent": _as_number(value(f"{QNAP_EXTERNAL}.7.0")),
    }
    warnings = _qnap_warnings(disks, raids, pools, volumes, system)
    detail = {
        "target": target,
        "profile": "qnap",
        "status": "degraded" if warnings else "online",
        "identity": {
            "model": value(f"{QNAP_SYSTEM}.3.0"),
            "hostname": value(f"{QNAP_SYSTEM}.4.0"),
            "firmware": value(f"{QNAP_SYSTEM}.6.0"),
        },
        "system": system,
        "disks": disks,
        "raids": raids,
        "storage_pools": pools,
        "volumes": volumes,
        "cache": cache,
        "ups": ups,
        "warnings": warnings,
        "updated_at": now,
    }
    samples = _qnap_samples(detail, now)
    return detail, samples


def _qnap_warnings(
    disks: list[dict[str, Any]], raids: list[dict[str, Any]], pools: list[dict[str, Any]],
    volumes: list[dict[str, Any]], system: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    healthy = {"good", "ready", "normal", "ok", "active", "optimal"}
    for prefix, items in (("disk", disks), ("raid", raids), ("volume", volumes)):
        for item in items:
            status = str(item.get("status") or "").strip().lower()
            if status and status not in healthy:
                warnings.append(f"{prefix}:{item.get('id') or item['index']}:{status}")
    for pool in pools:
        if pool.get("status") != "ready":
            warnings.append(f"pool:{pool.get('id') or pool['index']}:{pool.get('status')}")
    if system.get("power_status") == "failed":
        warnings.append("power:failed")
    return warnings


def _qnap_samples(detail: dict[str, Any], now: float) -> list[dict[str, Any]]:
    target = detail["target"]
    samples: list[dict[str, Any]] = []

    def add(name: str, raw: Any, unit: str = "") -> None:
        value = _as_number(raw)
        if value is not None:
            samples.append({"ts": now, "target": target, "metric": name, "value": value, "unit": unit})

    system = detail["system"]
    add("qnap_cpu_percent", system.get("cpu_percent"), "percent")
    add("qnap_cpu_temperature_celsius", system.get("cpu_temperature_celsius"), "celsius")
    add("qnap_system_temperature_celsius", system.get("system_temperature_celsius"), "celsius")
    add("qnap_memory_total_bytes", system.get("memory_total_bytes"), "bytes")
    add("qnap_memory_free_bytes", system.get("memory_free_bytes"), "bytes")
    add("qnap_memory_available_bytes", system.get("memory_available_bytes"), "bytes")
    add("qnap_memory_used_bytes", system.get("memory_used_bytes"), "bytes")
    add("qnap_uptime_seconds", system.get("uptime_seconds"), "seconds")
    if system.get("power_status") in {"ok", "failed"}:
        add("qnap_power_ok", 1 if system["power_status"] == "ok" else 0)
    for fan in system.get("fans", []):
        add(f"qnap_fan_speed_rpm_{_safe_metric_suffix(fan['index'])}", fan.get("speed_rpm"), "rpm")
    for disk in detail["disks"]:
        suffix = _safe_metric_suffix(disk["index"])
        add(f"qnap_disk_temperature_celsius_{suffix}", disk.get("temperature_celsius"), "celsius")
        add(f"qnap_disk_capacity_bytes_{suffix}", disk.get("capacity_bytes"), "bytes")
        status = str(disk.get("status") or "").strip().lower()
        add(f"qnap_disk_status_ok_{suffix}", 1 if status in {"good", "ready", "normal", "ok", "active", "optimal"} else 0)
    for kind, items in (("raid", detail["raids"]), ("pool", detail["storage_pools"]), ("volume", detail["volumes"])):
        for item in items:
            suffix = _safe_metric_suffix(item["index"])
            add(f"qnap_{kind}_capacity_bytes_{suffix}", item.get("capacity_bytes"), "bytes")
            add(f"qnap_{kind}_free_bytes_{suffix}", item.get("free_bytes"), "bytes")
    cache = detail["cache"]
    add("qnap_cache_read_hit_percent", cache.get("read_hit_percent"), "percent")
    add("qnap_cache_write_hit_percent", cache.get("write_hit_percent"), "percent")
    ups = detail["ups"]
    add("qnap_ups_load_percent", ups.get("load_percent"), "percent")
    add("qnap_ups_battery_percent", ups.get("battery_percent"), "percent")
    return samples


def _as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    number = _as_number(value)
    return int(number) if number is not None else None


def _safe_metric_suffix(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", value)[:48] or "unknown"
