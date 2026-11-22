import json
import time
from datetime import datetime, timezone

from src.config import (
    ANTHROPIC_API_KEY,
    CPU_THRESHOLD,
    MEMORY_THRESHOLD,
    DISK_THRESHOLD,
    POLL_INTERVAL_SECONDS,
)
from src.collectors import get_collector
from src.agent.agent_loop import diagnose
from src.storage.db import init_db, insert_incident, update_incident, get_open_incident

THRESHOLDS = {
    "cpu_percent": CPU_THRESHOLD,
    "memory_percent": MEMORY_THRESHOLD,
    "disk_percent": DISK_THRESHOLD,
}


def read_metrics(collector) -> dict[str, float]:
    return {
        "cpu_percent": collector.get_cpu_percent(),
        "memory_percent": collector.get_memory_detail()["percent"],
        "disk_percent": collector.get_disk_usage()["percent"],
    }


def run_diagnosis(collector, incident_id: int, metric: str, value: float) -> None:
    if not ANTHROPIC_API_KEY:
        print(f"[incident #{incident_id}] ANTHROPIC_API_KEY 미설정, 진단 건너뜀")
        return

    summary = f"{metric}={value} (임계값 {THRESHOLDS[metric]})"
    try:
        result = diagnose(collector, summary)
    except Exception as e:  # 진단 실패가 모니터링 루프를 멈추면 안 됨
        print(f"[incident #{incident_id}] 진단 실패: {type(e).__name__}: {e}")
        return

    fields = {"tool_calls_json": json.dumps(result["tool_calls"], ensure_ascii=False, default=str)}
    steps = len(result["tool_calls"])

    if result["status"] != "ok":
        update_incident(incident_id, **fields)
        print(f"[incident #{incident_id}] 진단 미완료: status={result['status']} ({steps} tool calls)")
        return

    diagnosis = result["result"]
    update_incident(
        incident_id,
        diagnosis=json.dumps(diagnosis, ensure_ascii=False),
        action_proposed=json.dumps(diagnosis["action"], ensure_ascii=False),
        **fields,
    )
    print(f"[incident #{incident_id}] 진단 완료 ({steps} tool calls, confidence={diagnosis['confidence']})")
    print(f"  원인: {diagnosis['root_cause']}")
    print(f"  조치 제안 [{diagnosis['action']['risk_level']}]: {diagnosis['action']['description']}")


def poll_once(collector) -> None:
    """지표별로 열린 인시던트가 없을 때만 새로 열고, 정상 복귀 시 닫는다."""
    metrics = read_metrics(collector)
    any_breach = False

    for metric, value in metrics.items():
        now = datetime.now(timezone.utc).isoformat()
        open_incident = get_open_incident(metric)

        if value >= THRESHOLDS[metric]:
            any_breach = True
            if open_incident is not None:
                continue
            incident_id = insert_incident(now, metric, value)
            print(f"[incident #{incident_id}] {metric}={value} at {now}")
            run_diagnosis(collector, incident_id, metric, value)
        elif open_incident is not None:
            update_incident(open_incident["id"], resolved_at=now)
            print(f"[incident #{open_incident['id']}] {metric}={value} 정상 복귀, resolved")

    if not any_breach:
        print("[monitor] ok")


def monitor_loop() -> None:
    init_db()
    collector = get_collector()
    print(f"[monitor] started with collector={type(collector).__name__}")

    while True:
        poll_once(collector)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    monitor_loop()
