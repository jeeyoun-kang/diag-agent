import subprocess

from .base import PsutilCollector


class LinuxCollector(PsutilCollector):
    DISK_PATH = "/"

    def read_recent_logs(self, n: int = 50) -> list[str]:
        try:
            result = subprocess.run(
                ["journalctl", "-n", str(n), "--no-pager"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.splitlines()
        except (FileNotFoundError, subprocess.SubprocessError):
            return []

    def check_service_status(self, service_name: str) -> dict:
        try:
            result = subprocess.run(
                [
                    "systemctl",
                    "show",
                    service_name,
                    "--property=LoadState,ActiveState,SubState,NRestarts,ActiveEnterTimestamp",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return {"service": service_name, "status": "unknown"}

        props = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if props.get("LoadState") == "not-found":
            return {"service": service_name, "status": "not_found"}
        return {
            "service": service_name,
            "status": props.get("ActiveState", "unknown"),
            "sub_state": props.get("SubState"),
            "restart_count": int(props["NRestarts"]) if props.get("NRestarts", "").isdigit() else None,
            "active_since": props.get("ActiveEnterTimestamp") or None,
        }
