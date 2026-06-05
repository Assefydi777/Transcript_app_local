from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

jobs_total = Counter("jobs_total", "Jobs processed by status", ["status"])
transcription_duration_seconds = Histogram("transcription_duration_seconds", "Transcription duration in seconds", ["model"])
ollama_request_duration_seconds = Histogram("ollama_request_duration_seconds", "Ollama request duration in seconds", ["model"])
transcript_queue_depth = Gauge("transcript_queue_depth", "Pending transcript jobs")

