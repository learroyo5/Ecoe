FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

# Run as an unprivileged user; /app/storage receives user uploads.
# NOTE for existing deployments: the backend_storage volume was created by
# root — run once before deploying:
#   docker run --rm -v ecoe_backend_storage:/s alpine chown -R 1000:1000 /s
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/storage \
    && chown -R app:app /app/storage

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
