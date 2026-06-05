from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

from config import get_settings
from metrics import ollama_request_duration_seconds

log = structlog.get_logger()


async def generate(prompt: str, model: str | None = None) -> str:
    settings = get_settings()
    selected_model = model or settings.ollama_model
    payload: dict[str, Any] = {"model": selected_model, "prompt": prompt, "stream": False, "format": "json"}
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            started = time.perf_counter()
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(f"{settings.ollama_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                ollama_request_duration_seconds.labels(model=selected_model).observe(time.perf_counter() - started)
                return str(data.get("response", ""))
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.HTTPError) as exc:
            last_error = exc
            log.warning("ollama_generate_retry", attempt=attempt + 1, error=str(exc))
            await asyncio.sleep(2**attempt)
    raise RuntimeError(f"Ollama generation failed: {last_error}")


async def health_check() -> bool:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            tags = await client.get(f"{settings.ollama_url}/api/tags")
            tags.raise_for_status()
            models = tags.json().get("models", [])
            names = {m.get("name") for m in models} | {str(m.get("name", "")).split(":")[0] for m in models}
            return settings.ollama_model in names or settings.ollama_model.split(":")[0] in names
    except Exception as exc:
        log.warning("ollama_health_failed", error=str(exc))
        return False
