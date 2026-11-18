"""Build the Feast offline feature table from the demo transactions."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from nexvia_fraud.features.service import FeatureService


def build_feast_features(csv_path: str | Path, out_path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path)
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
    service = FeatureService.from_dataframe(frame)
    names = service.feature_names()

    rows = []
    for row in frame.sort_values(["card_id", "event_time"]).itertuples(index=False):
        values = service.get_features(
            row.card_id,
            row.event_time,
            float(row.amount),
            row.device_id,
            row.email_domain,
            row.addr_id,
        )
        rows.append(
            {
                "transaction_id": row.transaction_id,
                "card_id": row.card_id,
                "event_timestamp": row.event_time,
                **{name: float(values[name]) for name in names},
            }
        )

    table = pd.DataFrame(rows)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(out, index=False)
    return table


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Feast offline table")
    parser.add_argument("--data", default="data/demo/transactions.csv")
    parser.add_argument("--out", default="data/features/transaction_features.parquet")
    args = parser.parse_args()
    table = build_feast_features(args.data, args.out)
    print(f"wrote {len(table)} feature rows to {args.out}")


if __name__ == "__main__":
    main()
