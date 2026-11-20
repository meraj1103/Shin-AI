# Multi-stage lightweight Python 3.12 container for Shin Cloud Brain
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY Shin/requirements-server.txt .
RUN pip install --no-cache-dir --user -r requirements-server.txt

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH \
    PYTHONPATH=/app/Shin:/app/Shin/core:/app

COPY --from=builder /root/.local /root/.local
COPY Shin /app/Shin

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')" || exit 1

CMD ["python", "-m", "uvicorn", "Shin.server.cloud_brain:app", "--host", "0.0.0.0", "--port", "8080"]
