#!/bin/bash
set -e

# Esegui le migration Alembic solo all'avvio dell'API (non dei worker Celery)
if [[ "${1}" == "uvicorn" ]]; then
    echo "▶ Running Alembic migrations..."
    alembic upgrade head
    echo "✓ Migrations complete."
fi

exec "$@"
