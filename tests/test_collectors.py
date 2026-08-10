from app.collectors.connectivity import ConnectivityCollector, parse_lan_probe_targets
from app.collectors.network import TrafficCollector
from app.collectors.prometheus import PrometheusExporterCollector, parse_exporter_targets, parse_prometheus_text
from app.collectors.snmp import (
    QNAP_STORAGE,
    QNAP_SYSTEM,
    PysnmpSession,
    SnmpCollector,
    _build_qnap_snapshot,
    _integer,
    _oid,
    _qnap_scalar_oids,
    _qnap_table_columns,
    _tlv,
)
from app.collectors.system import SystemCollector


def test_system_collector_returns_bounded_percentages():
    sample = SystemCollector().collect()
    assert 0 <= sample["cpu_percent"] <= 100
    assert 0 <= sample["memory_percent"] <= 100
    assert 0 <= sample["disk_percent"] <= 100


def test_traffic_collector_returns_non_negative_counters():
    collector = TrafficCollector()
    first = collector.collect()
    second = collector.collect()
    assert first["rx_bps"] >= 0
    assert second["tx_bps"] >= 0
    assert isinstance(second["interface"], str)


def test_connectivity_collector_summarizes_ping_and_dns(monkeypatch):
    collector = ConnectivityCollector(["192.168.10.1"], ["1.1.1.1"], "example.com")
    monkeypatch.setattr(collector._ping, "ping", lambda _: 3.2)
    monkeypatch.setattr(collector, "_dns_query", lambda *_: (True, 4.8, "1 answer"))
    checks = collector.collect()
    assert len(checks) == 2
    assert all(item["success"] for item in checks)
    assert {item["check_type"] for item in checks} == {"internet", "dns"}


def test_connectivity_collector_probes_lan_without_external_targets(monkeypatch):
    collector = ConnectivityCollector([], [], lan_targets=["gateway=icmp://192.168.10.1"])
    monkeypatch.setattr(collector._ping, "ping", lambda _: 1.7)
    checks = collector.collect()
    assert checks == [
        {
            "ts": checks[0]["ts"],
            "check_type": "lan_icmp",
            "target": "gateway",
            "success": True,
            "latency_ms": 1.7,
            "detail": "ICMP echo",
        }
    ]
    assert collector.internet_targets == ()
    assert collector.dns_servers == ()


def test_lan_probe_target_validation_requires_tcp_port():
    assert parse_lan_probe_targets(["nas=tcp://192.168.10.20:445"])[0].port == 445
    try:
        parse_lan_probe_targets(["nas=tcp://192.168.10.20"])
    except ValueError:
        pass
    else:
        raise AssertionError("TCP probe without a port was accepted")


def test_lan_probe_does_not_connect_to_public_address():
    collector = ConnectivityCollector([], [], lan_targets=["public=https://8.8.8.8/health"])
    check = collector.collect()[0]
    assert check["success"] is False
    assert "local address" in check["detail"]


def test_snmp_response_parser_reads_counter64():
    collector = SnmpCollector(["192.168.10.1"], "test")
    request_id = 12345
    varbind = _tlv(0x30, _oid("1.3.6.1.2.1.31.1.1.1.6.2") + _tlv(0x46, (987654).to_bytes(4, "big")))
    response_pdu = _tlv(0xA2, _integer(request_id) + _integer(0) + _integer(0) + _tlv(0x30, varbind))
    response = _tlv(0x30, _integer(1) + _tlv(0x04, b"test") + response_pdu)
    assert collector._parse_response(response, request_id) == 987654.0


def test_qnap_profile_normalizes_safe_system_and_storage_details():
    values = {
        f"{QNAP_SYSTEM}.3.0": "TS-464",
        f"{QNAP_SYSTEM}.4.0": "home-nas",
        f"{QNAP_SYSTEM}.6.0": "QTS 5.2",
        f"{QNAP_SYSTEM}.10.0": 48,
        f"{QNAP_SYSTEM}.12.0": 17,
        f"{QNAP_SYSTEM}.13.0": 8_000,
        f"{QNAP_SYSTEM}.16.0": 2_000,
        f"{QNAP_SYSTEM}.19.0": 0,
        f"{QNAP_SYSTEM}.21.0": 123_400,
        f"{QNAP_STORAGE}.2.1.2.1": 1,
        f"{QNAP_STORAGE}.2.1.3.1": "Vendor",
        f"{QNAP_STORAGE}.2.1.4.1": "Safe Model",
        f"{QNAP_STORAGE}.2.1.6.1": "SATA",
        f"{QNAP_STORAGE}.2.1.7.1": "Good",
        f"{QNAP_STORAGE}.2.1.8.1": 39,
        f"{QNAP_STORAGE}.2.1.9.1": 4_000,
        f"{QNAP_STORAGE}.5.1.2.1": 1,
        f"{QNAP_STORAGE}.5.1.3.1": "RAID 1",
        f"{QNAP_STORAGE}.5.1.4.1": "Ready",
        f"{QNAP_STORAGE}.5.1.5.1": 4_000,
        f"{QNAP_STORAGE}.5.1.7.1": "RAID1",
        f"{QNAP_STORAGE}.7.1.2.1": 1,
        f"{QNAP_STORAGE}.7.1.3.1": 4_000,
        f"{QNAP_STORAGE}.7.1.4.1": 1_000,
        f"{QNAP_STORAGE}.7.1.5.1": 0,
        f"{QNAP_STORAGE}.9.1.2.1": 1,
        f"{QNAP_STORAGE}.9.1.3.1": 4_000,
        f"{QNAP_STORAGE}.9.1.4.1": 1_000,
        f"{QNAP_STORAGE}.9.1.5.1": "Ready",
        f"{QNAP_STORAGE}.9.1.8.1": "DataVol1",
    }
    indices = {
        f"{QNAP_SYSTEM}.9.1.1": (),
        f"{QNAP_STORAGE}.2.1.1": ("1",),
        f"{QNAP_STORAGE}.5.1.1": ("1",),
        f"{QNAP_STORAGE}.7.1.1": ("1",),
        f"{QNAP_STORAGE}.9.1.1": ("1",),
    }
    detail, samples = _build_qnap_snapshot("192.168.10.20", values, indices, 100.0)
    assert detail["identity"] == {"model": "TS-464", "hostname": "home-nas", "firmware": "QTS 5.2"}
    assert detail["system"]["uptime_seconds"] == 1234
    assert detail["disks"][0]["status"] == "Good"
    assert detail["storage_pools"][0]["status"] == "ready"
    assert detail["warnings"] == []
    assert any(item["metric"] == "qnap_disk_temperature_celsius_1" for item in samples)
    assert "serial" not in str(detail).lower()


def test_snmpv3_qnap_security_requires_authpriv_without_exposing_secrets():
    session = PysnmpSession("3", "", "netpulse", "SHA", "auth-pass", "CBC-DES", "priv-pass", 2)
    assert session.auth_protocol == "SHA"
    assert session.priv_protocol == "DES"
    try:
        PysnmpSession("3", "", "netpulse", "SHA", "too-short", "DES", "short", 2)
    except ValueError as exc:
        assert "too-short" not in str(exc)
        assert "short" not in str(exc)
    else:
        raise AssertionError("invalid SNMPv3 credentials were accepted")


def test_qnap_queries_do_not_request_serial_number_oids():
    assert f"{QNAP_SYSTEM}.5.0" not in _qnap_scalar_oids()
    assert f"{QNAP_STORAGE}.2.1.5" not in {
        oid for columns in _qnap_table_columns().values() for oid in columns
    }


def test_prometheus_node_exporter_metrics_are_normalized(monkeypatch):
    target = "nas=http://192.168.10.20:9100/metrics"
    collector = PrometheusExporterCollector([target])
    first = parse_prometheus_text(
        """
        node_uname_info{machine="aarch64",nodename="nas",release="6.12",sysname="Linux"} 1
        node_cpu_seconds_total{cpu="0",mode="idle"} 80
        node_cpu_seconds_total{cpu="0",mode="user"} 20
        node_memory_MemTotal_bytes 1000
        node_memory_MemAvailable_bytes 400
        node_filesystem_size_bytes{device="/dev/sda1",fstype="ext4",mountpoint="/"} 2000
        node_filesystem_avail_bytes{device="/dev/sda1",fstype="ext4",mountpoint="/"} 500
        node_network_receive_bytes_total{device="eth0"} 10000
        node_network_transmit_bytes_total{device="eth0"} 4000
        node_network_receive_bytes_total{device="lo"} 999999
        node_boot_time_seconds 100
        node_hwmon_temp_celsius{chip="thermal"} 48.5
        """
    )
    second = parse_prometheus_text(
        """
        node_uname_info{machine="aarch64",nodename="nas",release="6.12",sysname="Linux"} 1
        node_cpu_seconds_total{cpu="0",mode="idle"} 86
        node_cpu_seconds_total{cpu="0",mode="user"} 24
        node_memory_MemTotal_bytes 1000
        node_memory_MemAvailable_bytes 400
        node_filesystem_size_bytes{device="/dev/sda1",fstype="ext4",mountpoint="/"} 2000
        node_filesystem_avail_bytes{device="/dev/sda1",fstype="ext4",mountpoint="/"} 500
        node_network_receive_bytes_total{device="eth0"} 12000
        node_network_transmit_bytes_total{device="eth0"} 5000
        node_boot_time_seconds 100
        node_hwmon_temp_celsius{chip="thermal"} 48.5
        """
    )
    clock = iter((10.0, 12.0))
    monkeypatch.setattr("app.collectors.prometheus.time.monotonic", lambda: next(clock))
    normalized_first = collector._normalize(collector.targets[0], first)
    normalized_second = collector._normalize(collector.targets[0], second)
    assert normalized_first["metadata"]["exporter_kind"] == "node_exporter"
    assert normalized_second["hostname"] == "nas"
    assert normalized_second["cpu_percent"] == 40.0
    assert normalized_second["memory_percent"] == 60.0
    assert normalized_second["disk_percent"] == 75.0
    assert normalized_second["temperature_c"] == 48.5
    assert normalized_second["rx_bps"] == 1000.0
    assert normalized_second["tx_bps"] == 500.0


def test_prometheus_exporter_targets_reject_credentials_and_queries():
    assert parse_exporter_targets(["nas=http://192.168.10.20:9100"])[0].url.endswith("/metrics")
    for value in (
        "nas=http://user:password@192.168.10.20:9100/metrics",
        "nas=http://192.168.10.20:9100/metrics?collect=cpu",
    ):
        try:
            parse_exporter_targets([value])
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe exporter target was accepted: {value}")


def test_prometheus_windows_exporter_current_metric_names_are_normalized(monkeypatch):
    collector = PrometheusExporterCollector(["pc=http://192.168.10.30:9182/metrics"])
    metrics = parse_prometheus_text(
        """
        windows_os_info{product="Windows 11 Pro",version="10.0.26100"} 1
        windows_cs_hostname{hostname="gaming-pc"} 1
        windows_cpu_time_total{core="0",mode="idle"} 100
        windows_cpu_time_total{core="0",mode="user"} 25
        windows_memory_physical_total_bytes 16000
        windows_memory_physical_free_bytes 4000
        windows_logical_disk_size_bytes{volume="C:"} 100000
        windows_logical_disk_free_bytes{volume="C:"} 25000
        windows_net_bytes_received_total{nic="Ethernet"} 3000
        windows_net_bytes_sent_total{nic="Ethernet"} 2000
        windows_system_system_up_time 3600
        """
    )
    monkeypatch.setattr("app.collectors.prometheus.time.monotonic", lambda: 10.0)
    normalized = collector._normalize(collector.targets[0], metrics)
    assert normalized["hostname"] == "gaming-pc"
    assert normalized["os_name"] == "Windows"
    assert normalized["memory_percent"] == 75.0
    assert normalized["disk_percent"] == 75.0
    assert normalized["uptime_seconds"] == 3600
