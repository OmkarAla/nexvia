.PHONY: setup data train gnn up down demo test lint k8s

setup:
	python -m pip install -e ".[dev]"

data:
	python -m nexvia_fraud.data.generate_demo --n 5000 --out data/demo/transactions.csv

data-real:
	mkdir -p data/raw/ieee
	kaggle competitions download -c ieee-fraud-detection -p data/raw/ieee
	cd data/raw/ieee && unzip -o '*.zip' && rm '*.zip'

train:
	python -m nexvia_fraud.models.train --data data/demo/transactions.csv --out artifacts/demo --run-id demo-001

gnn:
	python -m nexvia_fraud.models.gnn --data data/demo/transactions.csv --out artifacts/demo --run-id demo-gnn-001

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

feast:
	python scripts/build_feast_features.py
	python -c "from feast import FeatureStore; from feature_repo.features import CARD, views; FeatureStore(repo_path='feature_repo').apply([CARD, *views])"

k8s:
	kubectl kustomize k8s/overlays/kind > /dev/null
	echo "kustomize build OK"

lint:
	ruff check .
	ruff format --check .

ieee-data:
	kaggle competitions download -c ieee-fraud-detection -p data/raw/ieee --unzip
	python -m nexvia_fraud.data.load_ieee --data-dir data/raw/ieee --limit 150000
	python -c "from nexvia_fraud.models.train_ieee import load_raw; load_raw('data/raw/ieee', limit=30000).to_parquet('data/ieee/raw_30k.parquet', index=False)"

ieee-train:
	python -m nexvia_fraud.models.train_ieee --data data/ieee/raw_30k.parquet --out artifacts/ieee --run-id ieee-raw-001

feast-materialize:
	python scripts/build_feast_features.py
	python scripts/feast_materialize.py
