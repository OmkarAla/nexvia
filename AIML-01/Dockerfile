FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

COPY scripts ./scripts
COPY data ./data
COPY artifacts ./artifacts

EXPOSE 8000

CMD ["uvicorn", "nexvia_fraud.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
