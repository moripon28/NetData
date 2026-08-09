from app.collectors.connectivity import ConnectivityCollector
from app.collectors.network import TrafficCollector
from app.collectors.snmp import SnmpCollector, _integer, _oid, _tlv
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


def test_snmp_response_parser_reads_counter64():
    collector = SnmpCollector(["192.168.10.1"], "test")
    request_id = 12345
    varbind = _tlv(0x30, _oid("1.3.6.1.2.1.31.1.1.1.6.2") + _tlv(0x46, (987654).to_bytes(4, "big")))
    response_pdu = _tlv(0xA2, _integer(request_id) + _integer(0) + _integer(0) + _tlv(0x30, varbind))
    response = _tlv(0x30, _integer(1) + _tlv(0x04, b"test") + response_pdu)
    assert collector._parse_response(response, request_id) == 987654.0
