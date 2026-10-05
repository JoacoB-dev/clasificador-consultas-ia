#!/bin/sh
set -e
echo "Aplicando migraciones..."
alembic upgrade head
echo "Cargando datos de demo (si la base está vacía)..."
python -m app.seed
exec uvicorn app.main:app --host 0.0.0.0 --port 8083
