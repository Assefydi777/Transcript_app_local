#!/usr/bin/env bash
set -euo pipefail

SERVER="${1:-}"
if [[ -z "$SERVER" ]]; then
  echo "Usage: $0 SERVER"
  exit 1
fi

rsync -az --delete --exclude .git --exclude __pycache__ --exclude .env --exclude data/ ./ "deploy@$SERVER:/opt/transcript-app/"

ssh "deploy@$SERVER" '
set -euo pipefail
cd /opt/transcript-app
if [[ ! -f .env ]]; then
  if [[ -f .env.prod ]]; then
    cp .env.prod .env
  else
    echo "Missing /opt/transcript-app/.env.prod. Create it from .env.example first."
    exit 1
  fi
fi
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull || true
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans
docker compose exec -T app python scripts/healthcheck.py
'

echo "Deployment complete: http://$SERVER"

