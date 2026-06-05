from __future__ import annotations

import argparse
import asyncio
import os
import shutil
from pathlib import Path

import httpx
import redis
from sqlalchemy import text

from config import get_settings
from store.db import SessionLocal, init_db


async def run_cmd(*args: str) -> bool:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await proc.communicate()
    return proc.returncode == 0


async def check_ollama() -> tuple[bool, str]:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_url}/api/tags")
            response.raise_for_status()
            names = [m.get("name", "") for m in response.json().get("models", [])]
            ok = any(settings.ollama_model in name or settings.ollama_model.split(":")[0] == name.split(":")[0] for name in names)
            return ok, "ok" if ok else f"missing model; run: ollama pull {settings.ollama_model}"
    except Exception as exc:
        return False, str(exc)


async def check_db() -> tuple[bool, str]:
    try:
        await init_db()
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def check_redis() -> tuple[bool, str]:
    try:
        redis.Redis.from_url(get_settings().redis_url).ping()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def check_whisper_cache() -> tuple[bool, str]:
    cache_home = Path(os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface"))
    model_name = get_settings().whisper_model
    found = any(model_name in str(path) for path in cache_home.glob("**/*")) if cache_home.exists() else False
    return found, "ok" if found else f"model not found in {cache_home}"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("ffmpeg", await run_cmd("ffmpeg", "-version"), "ok"))
    if not args.quick:
        ok, msg = check_whisper_cache()
        checks.append(("whisper model", ok, msg))
        ok, msg = await check_ollama()
        checks.append(("ollama", ok, msg))
        ok, msg = check_redis()
        checks.append(("redis", ok, msg))
    ok, msg = await check_db()
    checks.append(("database", ok, msg))
    print(f"{'Check':<18} {'Status':<8} Details")
    print("-" * 48)
    failed = False
    for name, ok, msg in checks:
        failed = failed or not ok
        print(f"{name:<18} {('PASS' if ok else 'FAIL'):<8} {msg}")
    usage = shutil.disk_usage(get_settings().data_dir)
    print(f"{'disk':<18} {'INFO':<8} {usage.used // 1024 // 1024}MB / {usage.total // 1024 // 1024}MB")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

