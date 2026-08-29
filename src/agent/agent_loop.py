import json

import anthropic

from src.config import ANTHROPIC_API_KEY
from src.collectors.base import SystemCollector
from src.agent.tools import TOOL_DEFINITIONS, dispatch_tool_call

MODEL = "claude-sonnet-5"
MAX_STEPS = 6

SYSTEM_PROMPT = (
    "당신은 시스템 진단 에이전트입니다. 주어진 도구를 스스로 선택해 호출하며 "
    "가설을 세우고 검증하는 멀티스텝 추론으로 이상 현상의 근본 원인을 진단하세요. "
    "충분히 검증했다면 최종 진단문과 조치 제안을 텍스트로 답하세요."
)


def diagnose(collector: SystemCollector, trigger_summary: str) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": f"다음 이상 징후를 진단해줘: {trigger_summary}"}]
    tool_call_log = []

    for _ in range(MAX_STEPS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {"diagnosis": final_text, "tool_calls": tool_call_log}

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = dispatch_tool_call(collector, block.name, block.input)
            tool_call_log.append({"tool": block.name, "input": block.input, "result": result})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return {"diagnosis": "MAX_STEPS 도달, 진단 미완료", "tool_calls": tool_call_log}
