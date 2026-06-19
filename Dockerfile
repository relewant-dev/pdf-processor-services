FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY skills ./skills
COPY stationery ./stationery

RUN python -m pip install --upgrade pip \
    && python -m pip install -e .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "http_api:app", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8000"]