from __future__ import annotations

from pathlib import Path

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import get_settings
from ingest.watch_folder import enqueue_file

log = structlog.get_logger()
_seen: set[Path] = set()


async def poll_incoming() -> None:
    incoming = get_settings().data_dir / "incoming"
    for path in incoming.iterdir():
        if path.is_file() and path not in _seen:
            _seen.add(path)
            await enqueue_file(path)


def make_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_incoming, "interval", seconds=60, id="incoming_poll")
    return scheduler

