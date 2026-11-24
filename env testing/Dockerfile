FROM python:3.11-slim

LABEL maintainer="HEART C1 — G. L. S. Chanlaka (J26-SE-334)"
LABEL description="Containerized C1 Context-Aware Environmental Perturbation Engine FastAPI Microservice"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:/app/env testing"

RUN apt-get update && apt-get install -y --no-install-recommends \
    android-tools-adb \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY common /app/common
COPY ["env testing", "/app/env testing"]

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r "/app/env testing/requirements.txt" psutil python-multipart httpx

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8001/api/status || exit 1

WORKDIR "/app/env testing"
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
