import json
from types import SimpleNamespace

import pytest

from src.agent import agent_loop

VALID_DIAGNOSIS = {
    "summary": "stress 프로세스가 CPU 과점유",
    "root_cause": "stress 프로세스 폭주",
    "evidence": ["get_top_processes: stress 98%"],
    "confidence": "high",
    "action": {"description": "stress 프로세스 종료", "risk_level": "high"},
}


def tool_use(block_id, name, tool_input=None):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input or {})


def text(value):
    return SimpleNamespace(type="text", text=value)


def response(stop_reason, *content):
    usage = SimpleNamespace(input_tokens=100, output_tokens=10)
    return SimpleNamespace(stop_reason=stop_reason, content=list(content), usage=usage)


class FakeClient:
    """미리 정해둔 응답을 순서대로 돌려주고, 받은 요청을 기록한다."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        # messages 리스트는 루프가 계속 append하므로 호출 시점 스냅샷을 남긴다
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


class FakeCollector:
    def get_cpu_percent(self):
        return 97.0

    def get_top_processes(self, n=5):
        return [{"pid": 42, "name": "stress", "cpu_percent": 98.0, "memory_percent": 0.1}]

    def read_recent_logs(self, n=50):
        raise PermissionError("journal access denied")


@pytest.fixture
def fake_client(monkeypatch):
    def install(*responses):
        client = FakeClient(responses)
        monkeypatch.setattr(agent_loop.anthropic, "Anthropic", lambda **_: client)
        return client

    return install


def test_multistep_diagnosis_returns_structured_result(fake_client):
    client = fake_client(
        response("tool_use", tool_use("t1", "get_cpu_percent")),
        response("tool_use", tool_use("t2", "get_top_processes", {"n": 3})),
        response("end_turn", text(json.dumps(VALID_DIAGNOSIS, ensure_ascii=False))),
    )

    out = agent_loop.diagnose(FakeCollector(), "cpu_percent=97.0")

    assert out["status"] == "ok"
    assert out["result"] == VALID_DIAGNOSIS
    assert [c["tool"] for c in out["tool_calls"]] == ["get_cpu_percent", "get_top_processes"]
    assert out["usage"] == {"api_calls": 3, "input_tokens": 300, "output_tokens": 30}
    assert client.requests[0]["output_config"]["format"]["schema"] is agent_loop.DIAGNOSIS_SCHEMA

    second_turn_results = client.requests[1]["messages"][-1]["content"]
    assert second_turn_results[0]["tool_use_id"] == "t1"
    assert json.loads(second_turn_results[0]["content"]) == 97.0


def test_parallel_tool_calls_return_in_single_message(fake_client):
    client = fake_client(
        response("tool_use", tool_use("a", "get_cpu_percent"), tool_use("b", "get_top_processes")),
        response("end_turn", text(json.dumps(VALID_DIAGNOSIS))),
    )

    agent_loop.diagnose(FakeCollector(), "cpu")

    results = client.requests[1]["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"]


def test_tool_exception_is_reported_as_error_result(fake_client):
    client = fake_client(
        response("tool_use", tool_use("t1", "read_recent_logs"), tool_use("t2", "no_such_tool")),
        response("end_turn", text(json.dumps(VALID_DIAGNOSIS))),
    )

    out = agent_loop.diagnose(FakeCollector(), "cpu")

    assert out["status"] == "ok"
    results = client.requests[1]["messages"][-1]["content"]
    assert all(r["is_error"] for r in results)
    assert "PermissionError" in json.loads(results[0]["content"])
    assert "unknown tool" in json.loads(results[1]["content"])
    assert [c["is_error"] for c in out["tool_calls"]] == [True, True]


def test_max_steps_reached(fake_client):
    fake_client(*[response("tool_use", tool_use(f"t{i}", "get_cpu_percent")) for i in range(agent_loop.MAX_STEPS)])

    out = agent_loop.diagnose(FakeCollector(), "cpu")

    assert out["status"] == "max_steps"
    assert out["result"] is None
    assert len(out["tool_calls"]) == agent_loop.MAX_STEPS


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal"])
def test_truncated_or_refused_response(fake_client, stop_reason):
    fake_client(response(stop_reason, text('{"summary": "잘린')))

    out = agent_loop.diagnose(FakeCollector(), "cpu")

    assert out["status"] == stop_reason
    assert out["result"] is None


def test_unparseable_final_text(fake_client):
    fake_client(response("end_turn", text("not json")))

    assert agent_loop.diagnose(FakeCollector(), "cpu")["status"] == "invalid_output"
