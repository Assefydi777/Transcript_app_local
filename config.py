from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:////data/transcript.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://ollama:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    whisper_model: str = os.getenv("WHISPER_MODEL", "large-v3")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "auto")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "float16")
    whisper_language: str | None = os.getenv("WHISPER_LANGUAGE") or None
    enable_diarization: bool = os.getenv("ENABLE_DIARIZATION", "false").lower() == "true"
    hf_token: str | None = os.getenv("HF_TOKEN") or None
    data_dir: Path = Path(os.getenv("DATA_DIR", "/data"))
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "/data/outputs"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    allowed_hosts: list[str] = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]
    worker_concurrency: int = int(os.getenv("WORKER_CONCURRENCY", "1"))
    chunk_seconds: int = int(os.getenv("CHUNK_SECONDS", "30"))
    chunk_overlap_seconds: int = int(os.getenv("CHUNK_OVERLAP_SECONDS", "1"))
    max_prompt_tokens: int = int(os.getenv("MAX_PROMPT_TOKENS", "3000"))
    app_env: Literal["development", "production"] = os.getenv("APP_ENV", "development")  # type: ignore[assignment]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "incoming").mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "work").mkdir(parents=True, exist_ok=True)
    return settings

