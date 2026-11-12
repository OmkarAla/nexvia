import json
import os
import time
import uuid

import pandas as pd
import pytest
from sqlalchemy import select

from nexvia_fraud.config import Settings
from nexvia_fraud.db.engine import make_engine, make_session_factory
from nexvia_fraud.db.models import Alert, Transaction
from nexvia_fraud.db.repo import init_db
from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.scorer import Scorer
from nexvia_fraud.streaming.bus import KafkaConsumer, KafkaPublisher
from nexvia_fraud.streaming.consumer import handle_message

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("KAFKA_BOOTSTRAP"), reason="set KAFKA_BOOTSTRAP to run the stream test"
)
def test_publish_consume_score_persist():
    settings = Settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)

    frame = pd.read_csv(settings.demo_data_path)
    features = FeatureService.from_dataframe(frame)
    scorer = Scorer.load(settings.model_dir)

    transaction_id = f"it-{uuid.uuid4().hex[:12]}"
    row = frame.iloc[0]
    message = {
        "transaction_id": transaction_id,
        "card_id": row.card_id,
        "event_time": pd.Timestamp(row.event_time).isoformat(),
        "amount": float(row.amount),
        "device_id": row.device_id,
        "email_domain": row.email_domain,
        "addr_id": row.addr_id,
    }

    publisher = KafkaPublisher(settings.kafka_bootstrap)
    consumer = KafkaConsumer(
        settings.kafka_bootstrap,
        group_id=f"integration-{uuid.uuid4().hex[:8]}",
        topics=[settings.raw_topic],
    )

    try:
        publisher.publish(
            settings.raw_topic, key=str(row.card_id), value=json.dumps(message).encode()
        )
        publisher.flush()

        received = None
        deadline = time.time() + 30
        while time.time() < deadline:
            item = consumer.poll(1.0)
            if item is None:
                continue
            _topic, value = item
            payload = json.loads(value)
            if payload.get("transaction_id") == transaction_id:
                received = payload
                break
        assert received is not None, "message did not round-trip through Kafka"

        handle_message(received, features, scorer, session_factory, settings)
        consumer.commit()
    finally:
        consumer.close()

    with session_factory() as session:
        stored = session.get(Transaction, transaction_id)
        assert stored is not None
        assert 0.0 <= stored.score <= 1.0
        assert stored.model_version
        alert = session.scalar(select(Alert).where(Alert.transaction_id == transaction_id))
        assert alert is not None
        assert alert.status == "open"
