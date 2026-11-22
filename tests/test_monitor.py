import json

import pytest

from src import main
from src.storage import db


class FakeCollector:
    def __init__(self, cpu=10.0, memory=10.0, disk=10.0):
        self.cpu, self.memory, self.disk = cpu, memory, disk

    def get_cpu_percent(self):
        return self.cpu

    def get_memory_detail(self):
        return {"percent": self.memory}

    def get_disk_usage(self):
        return {"percent": self.disk}


SAMPLE_DIAGNOSIS = {
    "summary": "테스트 프로세스가 CPU 과점유",
    "root_cause": "원인: 테스트",
    "evidence": ["get_top_processes: stress 98%"],
    "confidence": "high",
    "action": {"description": "stress 프로세스 종료", "risk_level": "high"},
}


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


@pytest.fixture
def fake_diagnose(monkeypatch):
    calls = []

    def _diagnose(collector, summary):
        calls.append(summary)
        return {
            "status": "ok",
            "result": SAMPLE_DIAGNOSIS,
            "tool_calls": [{"tool": "get_cpu_percent", "input": {}, "result": 99, "is_error": False}],
        }

    monkeypatch.setattr(main, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(main, "diagnose", _diagnose)
    return calls


def test_breach_opens_incident_and_stores_diagnosis(temp_db, fake_diagnose):
    main.poll_once(FakeCollector(cpu=99.0))

    incident = db.get_open_incident("cpu_percent")
    assert incident["trigger_value"] == 99.0
    assert json.loads(incident["diagnosis"])["root_cause"] == "원인: 테스트"
    assert json.loads(incident["action_proposed"]) == SAMPLE_DIAGNOSIS["action"]
    assert json.loads(incident["tool_calls_json"])[0]["tool"] == "get_cpu_percent"
    assert len(fake_diagnose) == 1


def test_sustained_breach_does_not_duplicate(temp_db, fake_diagnose):
    collector = FakeCollector(cpu=99.0)
    for _ in range(3):
        main.poll_once(collector)

    assert len(fake_diagnose) == 1
    with db.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 1


def test_recovery_resolves_then_new_breach_reopens(temp_db, fake_diagnose):
    collector = FakeCollector(cpu=99.0)
    main.poll_once(collector)
    first_id = db.get_open_incident("cpu_percent")["id"]

    collector.cpu = 20.0
    main.poll_once(collector)
    assert db.get_open_incident("cpu_percent") is None
    assert db.get_incident(first_id)["resolved_at"] is not None

    collector.cpu = 95.0
    main.poll_once(collector)
    assert db.get_open_incident("cpu_percent")["id"] != first_id
    assert len(fake_diagnose) == 2


def test_diagnosis_failure_keeps_incident(temp_db, monkeypatch):
    def _boom(collector, summary):
        raise RuntimeError("api down")

    monkeypatch.setattr(main, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(main, "diagnose", _boom)

    main.poll_once(FakeCollector(memory=95.0))

    incident = db.get_open_incident("memory_percent")
    assert incident is not None
    assert incident["diagnosis"] is None


def test_missing_api_key_skips_diagnosis(temp_db, monkeypatch):
    monkeypatch.setattr(main, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(main, "diagnose", lambda *_: pytest.fail("diagnose should not be called"))

    main.poll_once(FakeCollector(disk=99.0))

    assert db.get_open_incident("disk_percent")["diagnosis"] is None


def test_update_incident_rejects_unknown_column(temp_db):
    incident_id = db.insert_incident("2026-01-01T00:00:00+00:00", "cpu_percent", 90.0)
    with pytest.raises(ValueError):
        db.update_incident(incident_id, trigger_value=0)


def test_incomplete_diagnosis_keeps_tool_calls_only(temp_db, monkeypatch):
    monkeypatch.setattr(main, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        main,
        "diagnose",
        lambda *_: {"status": "max_steps", "result": None, "tool_calls": [{"tool": "get_cpu_percent"}]},
    )

    main.poll_once(FakeCollector(cpu=99.0))

    incident = db.get_open_incident("cpu_percent")
    assert incident["diagnosis"] is None
    assert incident["action_proposed"] is None
    assert json.loads(incident["tool_calls_json"]) == [{"tool": "get_cpu_percent"}]


def test_connections_are_closed_after_use(temp_db):
    # 열린 연결이 남아 있으면 Windows에서는 DB 파일 삭제가 PermissionError로 실패한다
    incident_id = db.insert_incident("2026-01-01T00:00:00+00:00", "cpu_percent", 90.0)
    db.update_incident(incident_id, resolved_at="2026-01-01T00:01:00+00:00")
    db.get_incident(incident_id)

    db.DB_PATH.unlink()
