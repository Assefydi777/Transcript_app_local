# Transcript Summarizer

Self-hosted FastAPI application for uploading audio/video, converting media with FFmpeg, transcribing with faster-whisper, optionally diarizing with pyannote, and summarizing with a local Ollama model.

## Quick Start

```bash
cp .env.example .env
docker compose build
docker compose up -d
docker compose exec worker python scripts/seed_models.py --whisper-model base --ollama-model llama3.2
docker compose exec app python scripts/healthcheck.py
```

Open `http://localhost:8000`.

## Services

- `app`: FastAPI API and web UI
- `worker`: Redis Queue worker for transcription and summarization jobs
- `redis`: job queue
- `ollama`: local LLM runtime
- `prometheus` and `grafana`: optional lightweight monitoring

## Deployment

Production scripts live in `scripts/deploy/`. Run `setup_server.sh` once on Ubuntu 22.04, create `/opt/transcript-app/.env.prod`, then deploy with:

```bash
./scripts/deploy/deploy.sh YOUR_SERVER_IP
```

## Notes

Use `WHISPER_MODEL=base` for first local tests. Use `ENABLE_DIARIZATION=true` only after setting `HF_TOKEN`.

