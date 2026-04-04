.PHONY: help dev dev-build stop logs migrate makemigrations shell-api shell-db test prod prod-build

help:
	@echo ""
	@echo "  Corvin — Comandi disponibili"
	@echo "  ──────────────────────────────────────────"
	@echo "  make dev          Avvia l'ambiente di sviluppo"
	@echo "  make dev-build    Rebuild + avvia sviluppo"
	@echo "  make stop         Ferma tutti i container"
	@echo "  make logs         Log in tempo reale (api + worker)"
	@echo "  make migrate      Applica le migration al DB"
	@echo "  make makemigrations MSG='...'  Genera nuova migration"
	@echo "  make shell-api    Shell nel container API"
	@echo "  make shell-db     psql nel container DB"
	@echo "  make test         Esegui i test (in container)"
	@echo "  make prod         Avvia in produzione"
	@echo "  make prod-build   Rebuild + avvia produzione"
	@echo ""

# ── Sviluppo ─────────────────────────────────────────────────────────────────

dev:
	docker-compose up

dev-build:
	docker-compose up --build

stop:
	docker-compose down

logs:
	docker-compose logs -f corvin-api corvin-worker

migrate:
	docker-compose exec corvin-api alembic upgrade head

makemigrations:
	docker-compose exec corvin-api alembic revision --autogenerate -m "$(MSG)"

shell-api:
	docker-compose exec corvin-api bash

shell-db:
	docker-compose exec corvin-db psql -U $${POSTGRES_USER:-corvin} -d $${POSTGRES_DB:-corvin}

test:
	docker-compose exec corvin-api pytest tests/ -v --tb=short

# ── Produzione ────────────────────────────────────────────────────────────────

prod:
	docker-compose -f docker-compose.prod.yml up

prod-build:
	docker-compose -f docker-compose.prod.yml up --build
