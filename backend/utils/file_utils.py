from pathlib import Path
import shutil
from typing import Optional

from config import settings


# =========================
# BASE STORAGE PATH
# =========================

BASE_STORAGE_PATH = Path(settings.SCREENSHOT_STORAGE_PATH)


# =========================
# PATH BUILDERS
# =========================

def get_job_dir(job_id: int) -> Path:
    """
    Root directory for a crawl job
    storage/screenshots/{job_id}/
    """
    path = BASE_STORAGE_PATH / str(job_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_page_dir(job_id: int, page_id: int) -> Path:
    """
    Directory for a single crawled page
    storage/screenshots/{job_id}/{page_id}/
    """
    path = get_job_dir(job_id) / str(page_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_screenshot_path(
    job_id: int,
    page_id: int,
    chunk_index: int,
) -> Path:
    """
    Path for screenshot chunk
    storage/screenshots/{job_id}/{page_id}/chunk_{n}.png
    """
    page_dir = get_page_dir(job_id, page_id)
    return page_dir / f"chunk_{chunk_index}.png"


# =========================
# CLEANUP HELPERS
# =========================

def cleanup_job(job_id: int) -> None:
    """
    Remove all stored screenshots for a job
    Safe to call multiple times.
    """
    path = BASE_STORAGE_PATH / str(job_id)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def cleanup_page(job_id: int, page_id: int) -> None:
    """
    Remove screenshots for a single page
    """
    path = BASE_STORAGE_PATH / str(job_id) / str(page_id)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


# =========================
# UTILITIES
# =========================

def job_exists(job_id: int) -> bool:
    return (BASE_STORAGE_PATH / str(job_id)).exists()


def page_exists(job_id: int, page_id: int) -> bool:
    return (BASE_STORAGE_PATH / str(job_id) / str(page_id)).exists()
