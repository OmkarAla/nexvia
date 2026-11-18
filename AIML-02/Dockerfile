FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.4" "torchvision>=0.19" \
    && pip install .

COPY scripts ./scripts
COPY data/demo ./data/demo
COPY artifacts ./artifacts

EXPOSE 8000

CMD ["uvicorn", "nexvia_imaging.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
