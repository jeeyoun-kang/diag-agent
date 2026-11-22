import subprocess

import pytest

from src.collectors import get_collector, linux_collector
from src.collectors.linux_collector import LinuxCollector


def test_collector_returns_valid_metrics():
    collector = get_collector()

    assert 0 <= collector.get_cpu_percent() <= 100

    mem = collector.get_memory_detail()
    assert 0 <= mem["percent"] <= 100

    disk = collector.get_disk_usage()
    assert 0 <= disk["percent"] <= 100

    procs = collector.get_top_processes(3)
    assert len(procs) <= 3


def test_top_processes_reports_real_cpu_usage():
    procs = get_collector().get_top_processes(5)

    assert all(p["pid"] != 0 for p in procs)
    assert procs == sorted(procs, key=lambda p: p["cpu_percent"], reverse=True)
    # 샘플링이 제대로 되면 실행 중인 시스템에서 상위 프로세스가 전부 0.0일 수는 없다
    assert any(p["cpu_percent"] > 0 for p in procs)


def test_top_processes_sort_by_memory():
    procs = get_collector().get_top_processes(5, sort_by="memory")

    assert procs == sorted(procs, key=lambda p: p["memory_percent"], reverse=True)
    assert all(p["memory_rss_mb"] >= 0 for p in procs)


def test_top_processes_rejects_unknown_sort_key():
    with pytest.raises(ValueError):
        get_collector().get_top_processes(5, sort_by="disk")


def test_network_summary_shape():
    summary = get_collector().get_network_summary()

    assert summary["total_connections"] == sum(summary["status_counts"].values())
    assert isinstance(summary["listening_ports"], list)
    assert set(summary["interface_errors"]) == {"errin", "errout", "dropin", "dropout"}


def test_disk_io_rates_are_non_negative():
    io = get_collector().get_disk_io()

    for key in ("read_mb_per_sec", "write_mb_per_sec", "read_iops", "write_iops"):
        assert io[key] >= 0


def test_unknown_service_reports_not_found():
    status = get_collector().check_service_status("definitely-not-a-real-service-xyz")

    assert status["status"] in ("not_found", "unknown")


SYSTEMCTL_SHOW_OUTPUT = """LoadState=loaded
ActiveState=failed
SubState=failed
NRestarts=4
ActiveEnterTimestamp=Sun 2026-11-22 10:00:00 KST
"""


def test_linux_service_status_parses_systemctl_show(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout=SYSTEMCTL_SHOW_OUTPUT, stderr="")

    monkeypatch.setattr(linux_collector.subprocess, "run", fake_run)

    status = LinuxCollector().check_service_status("nginx")

    assert calls[0][:3] == ["systemctl", "show", "nginx"]
    assert status == {
        "service": "nginx",
        "status": "failed",
        "sub_state": "failed",
        "restart_count": 4,
        "active_since": "Sun 2026-11-22 10:00:00 KST",
    }


def test_linux_service_status_not_found(monkeypatch):
    monkeypatch.setattr(
        linux_collector.subprocess,
        "run",
        lambda cmd, **_: subprocess.CompletedProcess(cmd, 0, stdout="LoadState=not-found\n", stderr=""),
    )

    assert LinuxCollector().check_service_status("nope")["status"] == "not_found"


def test_windows_logs_report_unsupported_instead_of_empty():
    from src.agent.agent_loop import run_tool
    from src.collectors.windows_collector import WindowsCollector

    result, is_error = run_tool(WindowsCollector(), "read_recent_logs", {"n": 10})

    assert is_error
    assert "NotImplementedError" in result
