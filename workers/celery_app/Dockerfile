FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

COPY shared/ shared/
COPY agents/ agents/
COPY workers/ workers/
COPY services/ services/

# Run Celery worker
CMD ["celery", "-A", "workers.celery_app.app:celery_app", "worker", \
     "--loglevel=info", "--concurrency=4", "-Q", "review"]
