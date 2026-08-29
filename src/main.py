import time
from datetime import datetime, timezone

from src.config import CPU_THRESHOLD, MEMORY_THRESHOLD, DISK_THRESHOLD, POLL_INTERVAL_SECONDS
from src.collectors import get_collector
from src.storage.db import init_db, insert_incident


def check_thresholds(collector) -> list[tuple[str, float]]:
    breaches = []
    cpu = collector.get_cpu_percent()
    if cpu >= CPU_THRESHOLD:
        breaches.append(("cpu_percent", cpu))

    mem = collector.get_memory_detail()
    if mem["percent"] >= MEMORY_THRESHOLD:
        breaches.append(("memory_percent", mem["percent"]))

    disk = collector.get_disk_usage()
    if disk["percent"] >= DISK_THRESHOLD:
        breaches.append(("disk_percent", disk["percent"]))

    return breaches


def monitor_loop() -> None:
    init_db()
    collector = get_collector()
    print(f"[monitor] started with collector={type(collector).__name__}")

    while True:
        breaches = check_thresholds(collector)
        for metric, value in breaches:
            now = datetime.now(timezone.utc).isoformat()
            incident_id = insert_incident(now, metric, value)
            print(f"[incident #{incident_id}] {metric}={value} at {now}")
        if not breaches:
            print("[monitor] ok")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    monitor_loop()
