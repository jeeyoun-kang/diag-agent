from src.collectors.base import SystemCollector

TOOL_DEFINITIONS = [
    {
        "name": "get_cpu_percent",
        "description": "현재 CPU 사용률(%)을 조회한다.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_memory_detail",
        "description": "메모리 총량/사용량/사용률을 조회한다.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_top_processes",
        "description": "CPU 사용률 기준 상위 N개 프로세스를 조회한다.",
        "input_schema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "조회할 프로세스 수"}},
        },
    },
    {
        "name": "get_disk_usage",
        "description": "디스크 총량/사용량/사용률을 조회한다.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_recent_logs",
        "description": "최근 시스템 로그 N줄을 조회한다.",
        "input_schema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "조회할 로그 줄 수"}},
        },
    },
]


def dispatch_tool_call(collector: SystemCollector, name: str, tool_input: dict):
    if name == "get_cpu_percent":
        return collector.get_cpu_percent()
    if name == "get_memory_detail":
        return collector.get_memory_detail()
    if name == "get_top_processes":
        return collector.get_top_processes(tool_input.get("n", 5))
    if name == "get_disk_usage":
        return collector.get_disk_usage()
    if name == "read_recent_logs":
        return collector.read_recent_logs(tool_input.get("n", 50))
    raise ValueError(f"unknown tool: {name}")
