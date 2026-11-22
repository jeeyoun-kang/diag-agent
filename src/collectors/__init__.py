from src.config import IS_WINDOWS

from .base import SystemCollector
from .linux_collector import LinuxCollector
from .windows_collector import WindowsCollector


def get_collector() -> SystemCollector:
    if IS_WINDOWS:
        return WindowsCollector()
    return LinuxCollector()
