import time
from abc import ABC, abstractmethod
from collections import Counter

import psutil

CPU_SAMPLE_SECONDS = 1.0
SORT_KEYS = {"cpu": "cpu_percent", "memory": "memory_percent"}


def top_processes(n: int, sort_by: str = "cpu") -> list[dict]:
    """프로세스별 CPU/메모리를 측정해 sort_by 기준 상위 n개를 반환한다.

    psutil의 Process.cpu_percent()는 첫 호출 시 기준점만 잡고 0.0을 반환하므로,
    한 번 호출해 기준점을 잡은 뒤 샘플 구간 동안의 사용률을 다시 읽는다.
    """
    if sort_by not in SORT_KEYS:
        raise ValueError(f"sort_by must be one of {sorted(SORT_KEYS)}, got {sort_by!r}")

    procs = []
    for p in psutil.process_iter(["pid", "name"]):
        if p.pid == 0:  # Windows "System Idle Process": 유휴 CPU가 사용률처럼 집계됨
            continue
        try:
            p.cpu_percent(None)
            procs.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(CPU_SAMPLE_SECONDS)

    results = []
    for p in procs:
        try:
            results.append(
                {
                    "pid": p.pid,
                    "name": p.info["name"],
                    "cpu_percent": p.cpu_percent(None),
                    "memory_percent": round(p.memory_percent(), 2),
                    "memory_rss_mb": round(p.memory_info().rss / (1024**2), 1),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    results.sort(key=lambda r: r[SORT_KEYS[sort_by]], reverse=True)
    return results[:n]


def _process_name(pid: int | None) -> str | None:
    if not pid:
        return None
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def network_summary(top_n: int = 5) -> dict:
    """TCP/UDP 연결 상태 분포와 연결이 몰린 대상·포트·프로세스, 인터페이스 오류를 요약한다."""
    conns = psutil.net_connections(kind="inet")

    remote_ips = Counter(c.raddr.ip for c in conns if c.raddr)
    established_ports = Counter(
        c.laddr.port for c in conns if c.status == psutil.CONN_ESTABLISHED and c.laddr
    )
    by_pid = Counter(c.pid for c in conns if c.pid)
    io = psutil.net_io_counters()

    return {
        "total_connections": len(conns),
        "status_counts": dict(Counter(c.status for c in conns).most_common()),
        "listening_ports": sorted({c.laddr.port for c in conns if c.status == psutil.CONN_LISTEN}),
        "top_remote_ips": [{"ip": ip, "connections": n} for ip, n in remote_ips.most_common(top_n)],
        "top_established_local_ports": [
            {"port": port, "connections": n} for port, n in established_ports.most_common(top_n)
        ],
        "top_processes_by_connections": [
            {"pid": pid, "name": _process_name(pid), "connections": n}
            for pid, n in by_pid.most_common(top_n)
        ],
        "interface_errors": {
            "errin": io.errin,
            "errout": io.errout,
            "dropin": io.dropin,
            "dropout": io.dropout,
        },
    }


def disk_io_rates(sample_seconds: float = 1.0) -> dict:
    """샘플 구간 동안의 디스크 읽기/쓰기 처리량과 IOPS를 측정한다."""
    before = psutil.disk_io_counters()
    if before is None:
        raise RuntimeError("disk I/O counters unavailable on this system")
    time.sleep(sample_seconds)
    after = psutil.disk_io_counters()

    def per_sec(field: str) -> float:
        return (getattr(after, field) - getattr(before, field)) / sample_seconds

    result = {
        "read_mb_per_sec": round(per_sec("read_bytes") / (1024**2), 2),
        "write_mb_per_sec": round(per_sec("write_bytes") / (1024**2), 2),
        "read_iops": round(per_sec("read_count"), 1),
        "write_iops": round(per_sec("write_count"), 1),
    }
    if hasattr(before, "busy_time"):  # Linux 전용: 디스크가 요청을 처리하느라 바빴던 시간 비율
        result["busy_percent"] = round(per_sec("busy_time") / 10, 1)  # ms/s -> %
    return result


class SystemCollector(ABC):
    """AI 에이전트가 OS를 몰라도 동일 인터페이스로 호출하는 수집 어댑터."""

    @abstractmethod
    def get_cpu_percent(self) -> float:
        ...

    @abstractmethod
    def get_memory_detail(self) -> dict:
        ...

    @abstractmethod
    def get_top_processes(self, n: int = 5, sort_by: str = "cpu") -> list[dict]:
        ...

    @abstractmethod
    def get_disk_usage(self) -> dict:
        ...

    @abstractmethod
    def read_recent_logs(self, n: int = 50) -> list[str]:
        ...

    @abstractmethod
    def check_service_status(self, service_name: str) -> dict:
        ...

    @abstractmethod
    def get_network_summary(self) -> dict:
        ...

    @abstractmethod
    def get_disk_io(self) -> dict:
        ...


class PsutilCollector(SystemCollector):
    """psutil로 OS 공통 지표를 수집한다. 하위 클래스는 OS별로 다른 부분만 구현한다."""

    DISK_PATH: str

    def get_cpu_percent(self) -> float:
        return psutil.cpu_percent(interval=1)

    def get_memory_detail(self) -> dict:
        vm = psutil.virtual_memory()
        return {
            "total_gb": round(vm.total / (1024**3), 2),
            "used_gb": round(vm.used / (1024**3), 2),
            "percent": vm.percent,
        }

    def get_top_processes(self, n: int = 5, sort_by: str = "cpu") -> list[dict]:
        return top_processes(n, sort_by)

    def get_disk_usage(self) -> dict:
        usage = psutil.disk_usage(self.DISK_PATH)
        return {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "percent": usage.percent,
        }

    def get_network_summary(self) -> dict:
        return network_summary()

    def get_disk_io(self) -> dict:
        return disk_io_rates()
