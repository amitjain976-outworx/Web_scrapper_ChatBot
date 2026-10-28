from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    # =========================
    # APP
    # =========================
    APP_NAME: str = "Web Crawler ChatBot"
    ENV: str = "development"
    DEBUG: bool = True

    # =========================
    # DATABASE
    # =========================
    DATABASE_URL: str
    DB_ECHO: bool = False

    # =========================
    # AUTH / JWT
    # =========================
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    # =========================
    # CRAWLER LIMITS
    # =========================
    DEFAULT_MAX_DEPTH: int = 2
    ABSOLUTE_MAX_DEPTH: int = 10
    DEFAULT_MAX_PAGES: int = 50
    ABSOLUTE_MAX_PAGES: int = 10_000
    CRAWL_REQUEST_TIMEOUT: int = 30
    MAX_CONCURRENT_PAGES: int = 3

    # =========================
    # SCREENSHOT STORAGE
    # =========================
    SCREENSHOT_STORAGE_PATH: Path = Field(default=Path("storage/screenshots"))
    SCREENSHOT_FORMAT: str = "png"
    SCREENSHOT_CHUNK_HEIGHT: int = 1024

    # =========================
    # PLAYWRIGHT
    # =========================
    PLAYWRIGHT_BROWSER: str = "chromium"
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_NAV_TIMEOUT: int = 30_000

    # =========================
    # VECTOR DB (CHROMA - POC)
    # =========================
    CHROMA_PERSIST_PATH: str = Field(default="storage/chromadb")
    CHROMA_COLLECTION: str = "web_crawl_vectors"

    # =========================
    # RAG / LLM (DEFAULTS ONLY)
    # =========================
    LLM_MODEL_NAME: str = "llama3.1:8b"
    TEXT_LLM_MODEL: str = "llama3.2:latest"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_TOKENS: int = 2048
    TEXT_LLM_TIMEOUT: float
    RAG_TOP_K: int = 8

    OLLAMA_TIMEOUT: float = 1000.0
    VISION_MAX_IMAGE_SIZE: int = 1024
    PAGE_TIMEOUT_MS: int = 30_000
    OLLAMA_MODEL: str ="qwen3-vl:latest"

    # Screenshot timing
    SCREENSHOT_DELAY_MS: int = 10_000  # wait before taking screenshot

    # =========================
    # LOGGING
    # =========================
    LOG_LEVEL: str = "INFO"

    # Pydantic v2 config
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
