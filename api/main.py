from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes import jobs, search, status, summaries, transcripts
from config import get_settings
from ingest import api_routes as ingest_routes
from logging_config import configure_logging
from store.db import close_db, get_session, init_db
from store.models import Job
from summarize.ollama_client import health_check

configure_logging()
log = structlog.get_logger()
settings = get_settings()
templates = Jinja2Templates(directory="ui/templates")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    await health_check()
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(title="Transcript Summarizer", lifespan=lifespan)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

    @app.middleware("http")
    async def timing_logger(request: Request, call_next):  # type: ignore[no-untyped-def]
        started = time.perf_counter()
        response = await call_next(request)
        log.info("request", method=request.method, path=request.url.path, status=response.status_code, ms=round((time.perf_counter() - started) * 1000, 2))
        return response

    app.mount("/static", StaticFiles(directory="ui/static"), name="static")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(transcripts.router, prefix="/api")
    app.include_router(summaries.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(status.router, prefix="/api")
    app.include_router(ingest_routes.router, prefix="/api")

    Instrumentator().instrument(app).expose(app)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, session: Annotated[AsyncSession, Depends(get_session)]) -> HTMLResponse:
        recent = (await session.execute(select(Job).order_by(Job.created_at.desc()).limit(20))).scalars().all()
        return templates.TemplateResponse("index.html", {"request": request, "jobs": recent})

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    async def job_page(job_id: str, request: Request, session: Annotated[AsyncSession, Depends(get_session)]) -> HTMLResponse:
        job = await session.get(Job, job_id)
        return templates.TemplateResponse("job.html", {"request": request, "job": job, "job_id": job_id})

    @app.get("/search", response_class=HTMLResponse)
    async def search_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("search.html", {"request": request})

    return app


app = create_app()

