.PHONY: build up down logs test health seed

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f app worker

test:
	pytest tests/ -v

health:
	python scripts/healthcheck.py

seed:
	python scripts/seed_models.py

