import psutil

from .base import PsutilCollector


class WindowsCollector(PsutilCollector):
    DISK_PATH = "C:\\"

    def read_recent_logs(self, n: int = 50) -> list[str]:
        # 이벤트로그 연동(pywin32)은 후속 단계. 빈 리스트를 반환하면 에이전트가
        # "로그상 이상 없음"으로 오인하므로, 미지원임을 에러로 알린다.
        raise NotImplementedError("Windows 이벤트로그 조회는 아직 지원되지 않음 (로그 근거로 판단하지 말 것)")

    def check_service_status(self, service_name: str) -> dict:
        try:
            info = psutil.win_service_get(service_name).as_dict()
        except psutil.NoSuchProcess:
            return {"service": service_name, "status": "not_found"}
        return {
            "service": service_name,
            "status": info["status"],
            "start_type": info["start_type"],
            "pid": info["pid"],
            "display_name": info["display_name"],
        }
