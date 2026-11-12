"""Kafka consumer entry point."""

from __future__ import annotations

import logging

import pandas as pd

from nexvia_fraud.config import get_settings
from nexvia_fraud.db.engine import make_engine, make_session_factory
from nexvia_fraud.db.repo import init_db
from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.scorer import Scorer
from nexvia_fraud.streaming.bus import KafkaConsumer
from nexvia_fraud.streaming.consumer import run


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)

    features = FeatureService.from_dataframe(pd.read_csv(settings.demo_data_path))
    scorer = Scorer.load(settings.model_dir)

    consumer = KafkaConsumer(
        settings.kafka_bootstrap, group_id="fraud-scorer", topics=[settings.raw_topic]
    )
    run(consumer, features, scorer, session_factory, settings)


if __name__ == "__main__":
    main()
