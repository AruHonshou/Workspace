FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/app/backend/.venv/bin:$PATH

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
COPY backend /app/backend
WORKDIR /app/backend
RUN uv sync --frozen --no-dev

EXPOSE 8765
CMD ["uvicorn", "job_orchestrator.main:app", "--host", "0.0.0.0", "--port", "8765"]
