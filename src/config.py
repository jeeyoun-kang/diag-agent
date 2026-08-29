import os
import platform
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

CPU_THRESHOLD = float(os.getenv("CPU_THRESHOLD", 85))
MEMORY_THRESHOLD = float(os.getenv("MEMORY_THRESHOLD", 85))
DISK_THRESHOLD = float(os.getenv("DISK_THRESHOLD", 90))
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 30))

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "incidents.db"

IS_WINDOWS = platform.system() == "Windows"
