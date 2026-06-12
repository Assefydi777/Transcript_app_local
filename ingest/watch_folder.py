from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import redis
import structlog
from rq import Queue
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config import get_settings
from store.db import SessionLocal
from store.models import Job
from worker.job_runner import process_job

log = structlog.get_logger()


async def enqueue_file(path: Path) -> str:
    settings = get_settings()
    job_id = uuid.uuid4().hex
    async with SessionLocal() as session:
        session.add(Job(id=job_id, filename=path.name, source_path=str(path), status="pending", progress=0))
        await session.commit()
    queue = Queue("transcripts", connection=redis.Redis.from_url(settings.redis_url))
    queue.enqueue(process_job, job_id, str(path), job_id=job_id, job_timeout=settings.job_timeout_seconds)
    return job_id


class IncomingHandler(FileSystemEventHandler):
    def on_created(self, event: object) -> None:
        src_path = getattr(event, "src_path", "")
        is_directory = bool(getattr(event, "is_directory", False))
        if not is_directory and src_path:
            asyncio.run(enqueue_file(Path(src_path)))


def main() -> None:
    incoming = get_settings().data_dir / "incoming"
    observer = Observer()
    observer.schedule(IncomingHandler(), str(incoming), recursive=False)
    observer.start()
    try:
        while True:
            observer.join(1)
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
