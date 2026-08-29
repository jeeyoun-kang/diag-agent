import psutil

from .base import SystemCollector


class WindowsCollector(SystemCollector):
    def get_cpu_percent(self) -> float:
        return psutil.cpu_percent(interval=1)

    def get_memory_detail(self) -> dict:
        vm = psutil.virtual_memory()
        return {
            "total_gb": round(vm.total / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "percent": vm.percent,
        }

    def get_top_processes(self, n: int = 5) -> list[dict]:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            procs.append(p.info)
        procs.sort(key=lambda p: p["cpu_percent"] or 0, reverse=True)
        return procs[:n]

    def get_disk_usage(self) -> dict:
        usage = psutil.disk_usage("C:\\")
        return {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "percent": usage.percent,
        }

    def read_recent_logs(self, n: int = 50) -> list[str]:
        # Phase 1 뼈대: Windows 이벤트로그 연동은 후속 단계에서 pywin32로 구현
        return []
