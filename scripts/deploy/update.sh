#!/usr/bin/env bash
set -euo pipefail

cd /opt/transcript-app
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps worker
docker compose exec -T app python scripts/healthcheck.py --quick || { docker compose logs worker; exit 1; }
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps app
docker compose exec -T app python scripts/healthcheck.py || { docker compose logs app; exit 1; }
echo "Update complete."

