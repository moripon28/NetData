from __future__ import annotations

import random
import socket
import time
from dataclasses import dataclass
from typing import Any, Iterable


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


class SnmpCollector:
    """Minimal read-only SNMPv2c GET client with no native dependencies."""

    def __init__(
        self,
        targets: Iterable[str],
        community: str,
        interface_index: int = 2,
        extra_oids: Iterable[str] = (),
    ) -> None:
        self.targets = tuple(dict.fromkeys(targets))
        self.community = community.encode("utf-8")
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

    def collect(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        samples: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        now = time.time()
        for target in self.targets:
            for metric in self.metrics:
                try:
                    raw_value = self._get(target, metric.oid)
                    if not isinstance(raw_value, float):
                        continue
                    samples.append(
                        {"ts": now, "target": target, "metric": metric.name, "value": raw_value, "unit": metric.unit}
                    )
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
                except (OSError, TimeoutError, ValueError) as exc:
                    errors.append({"target": target, "metric": metric.name, "error": type(exc).__name__})
        return samples, errors

    def _get(self, target: str, oid: str) -> float | str:
        request_id = random.randint(1, 2_000_000_000)
        varbind = _tlv(0x30, _oid(oid) + _tlv(0x05, b""))
        varbinds = _tlv(0x30, varbind)
        pdu = _tlv(0xA0, _integer(request_id) + _integer(0) + _integer(0) + varbinds)
        message = _tlv(0x30, _integer(1) + _tlv(0x04, self.community) + pdu)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1.5)
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
