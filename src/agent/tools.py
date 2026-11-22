from src.collectors.base import SystemCollector, SORT_KEYS

TOOL_DEFINITIONS = [
    {
        "name": "get_cpu_percent",
        "description": "현재 시스템 전체 CPU 사용률(%)을 조회한다. 전체 코어 합산 기준이라 0~100 범위다.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_memory_detail",
        "description": "메모리 총량/사용량/사용률을 조회한다.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_top_processes",
        "description": (
            "CPU 또는 메모리 사용량 기준 상위 N개 프로세스를 조회한다. "
            "각 항목에 cpu_percent, memory_percent, memory_rss_mb가 모두 포함된다. "
            "프로세스별 cpu_percent는 코어 1개=100% 기준이라 멀티코어에서는 100을 넘을 수 있다. "
            "메모리 문제를 추적할 때는 sort_by=memory를 사용하라."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "조회할 프로세스 수 (기본 5)"},
                "sort_by": {
                    "type": "string",
                    "enum": sorted(SORT_KEYS),
                    "description": "정렬 기준 (기본 cpu)",
                },
            },
        },
    },
    {
        "name": "get_disk_usage",
        "description": "디스크 총량/사용량/사용률을 조회한다.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_disk_io",
        "description": (
            "1초간 디스크 읽기/쓰기 처리량(MB/s)과 IOPS를 측정한다. "
            "용량은 여유 있는데 시스템이 느릴 때 I/O 병목을 확인하는 데 쓴다. "
            "Linux에서는 디스크가 바빴던 시간 비율(busy_percent)도 포함된다."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_network_summary",
        "description": (
            "네트워크 연결 상태를 요약한다: 상태별 연결 수(ESTABLISHED, TIME_WAIT 등), "
            "리스닝 포트, 연결이 몰린 원격 IP·로컬 포트·프로세스, 인터페이스 오류/드롭 누적값. "
            "연결 폭주, 연결 누수, 특정 클라이언트 과다 접속을 확인하는 데 쓴다."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "check_service_status",
        "description": (
            "서비스 상태를 조회한다 (Linux: systemd 유닛, Windows: Windows 서비스). "
            "실행 상태와 Linux에서는 재시작 횟수·활성화 시각을 반환한다. "
            "존재하지 않는 서비스면 status=not_found."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "서비스 이름 (예: nginx, sshd, Spooler)",
                },
            },
            "required": ["service_name"],
        },
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
        return collector.get_top_processes(tool_input.get("n", 5), tool_input.get("sort_by", "cpu"))
    if name == "get_disk_usage":
        return collector.get_disk_usage()
    if name == "get_disk_io":
        return collector.get_disk_io()
    if name == "get_network_summary":
        return collector.get_network_summary()
    if name == "check_service_status":
        return collector.check_service_status(tool_input["service_name"])
    if name == "read_recent_logs":
        return collector.read_recent_logs(tool_input.get("n", 50))
    raise ValueError(f"unknown tool: {name}")
