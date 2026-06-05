from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import redis
import structlog
from prometheus_client import start_http_server
from rq import Queue, Worker

from config import get_settings
from logging_config import configure_logging
from metrics import jobs_total, transcription_duration_seconds, transcript_queue_depth
from store.db import SessionLocal, init_db, update_fts
from store.file_writer import write_outputs
from store.models import Job, Summary, Transcript
from summarize.ollama_client import generate
from summarize.postprocess import parse_summary
from summarize.prompt_builder import build_prompt_plan
from worker.diarize import diarize_segments
from worker.preprocess import preprocess_file
from worker.transcribe import transcribe_chunks

configure_logging()
log = structlog.get_logger()


async def _set_job(job_id: str, **values: Any) -> None:
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if job:
            for key, value in values.items():
                setattr(job, key, value)
            await session.commit()
    if "status" in values:
        jobs_total.labels(status=str(values["status"])).inc()


async def process_job_async(job_id: str, source_path: str) -> None:
    await init_db()
    await _set_job(job_id, status="preprocessing", progress=5)
    try:
        info, wav_path, chunks = await preprocess_file(Path(source_path), job_id)
        await _set_job(job_id, duration=info.duration, status="transcribing", progress=20)
        transcribe_started = time.perf_counter()
        segments, language = await transcribe_chunks(chunks)
        transcription_duration_seconds.labels(model=get_settings().whisper_model).observe(time.perf_counter() - transcribe_started)
        await _set_job(job_id, status="diarizing", progress=65)
        segments = await diarize_segments(wav_path, segments)
        text = "\n".join(str(segment.get("text", "")).strip() for segment in segments)
        await _set_job(job_id, status="summarizing", progress=75)
        plan = build_prompt_plan(segments)
        raw_outputs = [await generate(prompt) for prompt in plan.prompts]
        if plan.reduce_prompt:
            raw = await generate(plan.reduce_prompt.format(chunk_summaries="\n\n".join(raw_outputs)))
        else:
            raw = raw_outputs[0]
        parsed = parse_summary(raw)
        async with SessionLocal() as session:
            session.add(Transcript(job_id=job_id, text=text, segments=segments, language=language))
            session.add(
                Summary(
                    job_id=job_id,
                    tldr=parsed.tldr,
                    bullets=parsed.bullets,
                    action_items=parsed.action_items,
                    keywords=parsed.keywords,
                    topics=parsed.topics,
                    raw_response=parsed.raw_response,
                )
            )
            await update_fts(session, job_id, text, "\n".join([parsed.tldr, *parsed.bullets, *parsed.action_items]))
            await session.commit()
        await write_outputs(job_id, segments, parsed.to_dict())
        await _set_job(job_id, status="done", progress=100)
    except Exception as exc:
        log.exception("job_failed", job_id=job_id, error=str(exc))
        await _set_job(job_id, status="failed", error=str(exc), progress=100)
        raise


def process_job(job_id: str, source_path: str) -> None:
    asyncio.run(process_job_async(job_id, source_path))


async def heartbeat(redis_url: str) -> None:
    client = redis.Redis.from_url(redis_url)
    while True:
        client.set("worker:heartbeat", "alive", ex=30)
        await asyncio.sleep(10)


def main() -> None:
    settings = get_settings()
    start_http_server(9001)
    redis_conn = redis.Redis.from_url(settings.redis_url)
    queue = Queue("transcripts", connection=redis_conn)
    transcript_queue_depth.set(queue.count)
    worker = Worker([queue], connection=redis_conn)
    log.info("worker_started", queues=["transcripts"])
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
