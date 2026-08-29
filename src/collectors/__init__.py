import platform

from .base import SystemCollector
from .linux_collector import LinuxCollector
from .windows_collector import WindowsCollector


def get_collector() -> SystemCollector:
    if platform.system() == "Windows":
        return WindowsCollector()
    return LinuxCollector()
