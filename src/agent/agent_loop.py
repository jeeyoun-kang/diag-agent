import json

import anthropic

from src.config import ANTHROPIC_API_KEY
from src.collectors.base import SystemCollector
from src.agent.tools import TOOL_DEFINITIONS, dispatch_tool_call

MODEL = "claude-sonnet-5"
MAX_STEPS = 6
MAX_TOKENS = 16000

SYSTEM_PROMPT = (
    "당신은 시스템 진단 에이전트입니다. 주어진 도구를 스스로 선택해 호출하며 "
    "가설을 세우고 검증하는 멀티스텝 추론으로 이상 현상의 근본 원인을 진단하세요. "
    "도구가 오류를 반환하면 다른 도구로 우회해 검증을 이어가세요. "
    "충분히 검증했다면 최종 진단을 지정된 JSON 형식으로 답하세요. "
    "조치의 risk_level은 되돌리기 쉬운 조치(캐시 정리 등)는 low, 서비스 재시작은 medium, "
    "프로세스 강제 종료·데이터 삭제는 high로 분류하세요."
)

RISK_LEVELS = ["low", "medium", "high"]

DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "한두 문장 요약"},
        "root_cause": {"type": "string", "description": "근본 원인"},
        "evidence": {
            "type": "array",
            "items": {"type": "string"},
            "description": "원인을 뒷받침하는 도구 조회 결과",
        },
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "action": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "제안하는 조치"},
                "risk_level": {"type": "string", "enum": RISK_LEVELS},
            },
            "required": ["description", "risk_level"],
            "additionalProperties": False,
        },
    },
    "required": ["summary", "root_cause", "evidence", "confidence", "action"],
    "additionalProperties": False,
}


def run_tool(collector: SystemCollector, name: str, tool_input: dict) -> tuple[object, bool]:
    """도구를 실행하고 (결과, 에러여부)를 반환한다. 예외는 루프를 멈추지 않고 에이전트에게 전달된다."""
    try:
        return dispatch_tool_call(collector, name, tool_input), False
    except Exception as e:
        return f"{type(e).__name__}: {e}", True


def diagnose(collector: SystemCollector, trigger_summary: str) -> dict:
    """멀티스텝 진단을 수행한다.

    반환: {"status", "result", "tool_calls", "usage"}
      status: ok | max_steps | max_tokens | refusal | invalid_output
      result: status가 ok일 때 DIAGNOSIS_SCHEMA를 따르는 dict, 그 외 None
      usage: 전체 API 호출에 걸친 토큰 합계와 호출 횟수
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": f"다음 이상 징후를 진단해줘: {trigger_summary}"}]
    tool_call_log = []
    usage = {"api_calls": 0, "input_tokens": 0, "output_tokens": 0}

    def finish(status: str, result: dict | None = None) -> dict:
        return {"status": status, "result": result, "tool_calls": tool_call_log, "usage": usage}

    for _ in range(MAX_STEPS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
            output_config={"format": {"type": "json_schema", "schema": DIAGNOSIS_SCHEMA}},
        )
        messages.append({"role": "assistant", "content": response.content})
        usage["api_calls"] += 1
        usage["input_tokens"] += response.usage.input_tokens
        usage["output_tokens"] += response.usage.output_tokens

        if response.stop_reason in ("max_tokens", "refusal"):
            return finish(response.stop_reason)

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            try:
                return finish("ok", json.loads(final_text))
            except json.JSONDecodeError:
                return finish("invalid_output")

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result, is_error = run_tool(collector, block.name, block.input)
            tool_call_log.append(
                {"tool": block.name, "input": block.input, "result": result, "is_error": is_error}
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return finish("max_steps")
