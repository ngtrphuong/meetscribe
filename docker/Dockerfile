FROM nvidia/cuda:12.6.3-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    ffmpeg libsqlcipher-dev git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Editable install needs package sources (setuptools packages.find backend*)
COPY pyproject.toml README.md ./
COPY backend/ backend/
RUN python3.11 -m pip install --no-cache-dir -e ".[dev]"

COPY engines/ engines/
COPY scripts/ scripts/

RUN mkdir -p /app/data/recordings /app/data/models

EXPOSE 9876

CMD ["python3.11", "-m", "uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", "--port", "9876", \
     "--workers", "1", "--loop", "uvloop", "--http", "httptools"]
