.PHONY: setup data up down test lint

setup:
	python -m pip install -e ".[dev]"

data:
	python -m nexvia_imaging.data.make_dicom --out data/demo

up:
	docker compose up --build -d

down:
	docker compose down -v

test:
	python -m pytest -q

lint:
	ruff check .
	ruff format --check .
