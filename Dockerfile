FROM python:3.10-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libmariadb-dev-compat \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p models logs/summary/daily logs/summary/weekly data

ENV DB_HOST=host.docker.internal \
    DB_PORT=3306 \
    DB_USER=root \
    DB_PASS="" \
    DB_NAME=Asentinel \
    LLM_MODEL=llama-3.3-70b-versatile \
    LLM_TEMPERATURE=0.3 \
    LLM_MAX_TOKENS=500 \
    PYTHONUNBUFFERED=1

VOLUME ["/app/models", "/app/logs", "/app/data"]

CMD ["python", "main.py"]
