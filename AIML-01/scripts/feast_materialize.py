"""Materialize the offline feature table into the Feast online store."""

from __future__ import annotations

import argparse

import pandas as pd

from nexvia_fraud.config import get_settings
from nexvia_fraud.features.feast_service import apply_and_materialize


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Apply and materialize Feast")
    parser.add_argument("--repo", default=settings.feast_repo_path)
    parser.add_argument(
        "--features", default="data/features/transaction_features.parquet"
    )
    args = parser.parse_args()

    table = pd.read_parquet(args.features)
    start = table["event_timestamp"].min().to_pydatetime()
    end = (table["event_timestamp"].max() + pd.Timedelta(days=1)).to_pydatetime()

    apply_and_materialize(args.repo, start, end)
    print(f"materialized {len(table):,} rows from {start} to {end}")


if __name__ == "__main__":
    main()
