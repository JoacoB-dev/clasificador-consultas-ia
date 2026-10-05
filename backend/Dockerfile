FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8083
# Migra, carga la demo y levanta la API (el worker usa la misma imagen con otro comando)
CMD ["sh", "docker-entrypoint.sh"]
