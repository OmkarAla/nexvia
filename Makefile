.PHONY: setup data train up down demo test lint

setup:
	python -m pip install -e ".[dev]"
	python -m pre_commit install || true

data:
	python -m nexvia_fraud.data.generate_demo --n 5000 --out data/demo/transactions.csv

train:
	python -m nexvia_fraud.models.train --data data/demo/transactions.csv --out artifacts/demo --run-id demo-001

up:
	docker compose up --build -d

down:
	docker compose down -v

demo:
	python scripts/seed.py
	python scripts/replay.py --rate 2

test:
	python -m pytest -q

test-integration:
	python -m pytest -m integration -q

lint:
	ruff check .
	ruff format --check .
