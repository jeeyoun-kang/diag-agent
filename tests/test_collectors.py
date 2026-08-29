from src.collectors import get_collector


def test_collector_returns_valid_metrics():
    collector = get_collector()

    assert 0 <= collector.get_cpu_percent() <= 100

    mem = collector.get_memory_detail()
    assert 0 <= mem["percent"] <= 100

    disk = collector.get_disk_usage()
    assert 0 <= disk["percent"] <= 100

    procs = collector.get_top_processes(3)
    assert len(procs) <= 3
