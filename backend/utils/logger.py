import logging
import sys
from pathlib import Path
from datetime import datetime

from config import settings

# =========================
# LOG FORMAT
# =========================

LOG_FORMAT = (
    "%(asctime)s | "
    "%(levelname)s | "
    "%(name)s | "
    "%(message)s"
)

# =========================
# LOG DIRECTORY
# =========================

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# =========================
# LOGGER FACTORY
# =========================

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance.
    One log file per day: logs_ddmmyyyy.log
    Safe on Windows + uvicorn reload.
    """
    logger = logging.getLogger(name)
    logger.setLevel(settings.LOG_LEVEL)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(LOG_FORMAT)

    # -------------------------
    # Console handler
    # -------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # -------------------------
    # Daily file handler
    # -------------------------
    date_str = datetime.now().strftime("%d%m%Y")
    log_file = LOG_DIR / f"logs_{date_str}.log"

    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8",
        delay=True  # 🔑 prevents Windows file lock issues
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.propagate = False

    return logger
