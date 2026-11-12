"""Seed the demo database by scoring a bounded slice of the synthetic data."""

from __future__ import annotations

import argparse

import pandas as pd

from nexvia_fraud.config import get_settings
from nexvia_fraud.db.engine import make_engine, make_session_factory
from nexvia_fraud.db.repo import init_db
from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.scorer import Scorer
from nexvia_fraud.scoring import score_transaction


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo transactions and alerts")
    parser.add_argument("--limit", type=int, default=600)
    args = parser.parse_args()

    settings = get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)

    frame = pd.read_csv(settings.demo_data_path)
    features = FeatureService.from_dataframe(frame)
    scorer = Scorer.load(settings.model_dir)

    seeded = 0
    alerts = 0
    for row in frame.sort_values("event_time").head(args.limit).itertuples(index=False):
        result = score_transaction(
            {
                "transaction_id": row.transaction_id,
                "card_id": row.card_id,
                "event_time": pd.Timestamp(row.event_time).isoformat(),
                "amount": float(row.amount),
                "device_id": row.device_id,
                "email_domain": row.email_domain,
                "addr_id": row.addr_id,
            },
            features,
            scorer,
            session_factory,
            settings.alert_threshold,
        )
        seeded += 1
        if result.score >= settings.alert_threshold:
            alerts += 1

    print(f"seeded {seeded} transactions, {alerts} above threshold {settings.alert_threshold}")


if __name__ == "__main__":
    main()
