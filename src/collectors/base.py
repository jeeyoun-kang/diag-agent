from abc import ABC, abstractmethod


class SystemCollector(ABC):
    """AI 에이전트가 OS를 몰라도 동일 인터페이스로 호출하는 수집 어댑터."""

    @abstractmethod
    def get_cpu_percent(self) -> float:
        ...

    @abstractmethod
    def get_memory_detail(self) -> dict:
        ...

    @abstractmethod
    def get_top_processes(self, n: int = 5) -> list[dict]:
        ...

    @abstractmethod
    def get_disk_usage(self) -> dict:
        ...

    @abstractmethod
    def read_recent_logs(self, n: int = 50) -> list[str]:
        ...
