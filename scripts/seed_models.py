from __future__ import annotations

import argparse
import asyncio
import json

import httpx

from config import get_settings


async def seed_whisper(model_name: str) -> None:
    from faster_whisper.utils import download_model

    await asyncio.to_thread(download_model, model_name)
    print(f"Whisper model ready: {model_name}")


async def seed_ollama(model_name: str) -> None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=None) as client:
        tags = await client.get(f"{settings.ollama_url}/api/tags")
        if tags.status_code == 200:
            names = [m.get("name", "") for m in tags.json().get("models", [])]
            if any(model_name in name or model_name.split(":")[0] == name.split(":")[0] for name in names):
                print(f"Ollama model ready: {model_name}")
                return
        async with client.stream("POST", f"{settings.ollama_url}/api/pull", json={"name": model_name, "stream": True}) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line:
                    payload = json.loads(line)
                    print(payload.get("status", line))


async def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("--whisper-model", default=settings.whisper_model)
    parser.add_argument("--ollama-model", default=settings.ollama_model)
    args = parser.parse_args()
    await seed_whisper(args.whisper_model)
    await seed_ollama(args.ollama_model)


if __name__ == "__main__":
    asyncio.run(main())

