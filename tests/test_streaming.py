import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from nexvia_fraud.config import Settings
from nexvia_fraud.db.models import Alert, Base, Transaction
from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.scorer import Scorer
from nexvia_fraud.models.train import train_model
from nexvia_fraud.streaming.bus import InMemoryBus
from nexvia_fraud.streaming.consumer import handle_message
from nexvia_fraud.streaming.producer import replay


@pytest.fixture(scope="module")
def stream_model(demo_df, tmp_path_factory):
    out = tmp_path_factory.mktemp("stream-model")
    train_model(demo_df, out, "stream-test")
    return out


@pytest.fixture
def stream_env(demo_df, stream_model):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return {
        "features": FeatureService.from_dataframe(demo_df),
        "scorer": Scorer.load(stream_model),
        "factory": factory,
        "settings": Settings(alert_threshold=0.0),
    }


def _message(row, transaction_id="stream-1"):
    return {
        "transaction_id": transaction_id,
        "card_id": row.card_id,
        "event_time": row.event_time.isoformat(),
        "amount": float(row.amount),
        "device_id": row.device_id,
        "email_domain": row.email_domain,
        "addr_id": row.addr_id,
    }


def test_in_memory_roundtrip():
    bus = InMemoryBus()
    bus.publish("transactions.raw", "card-1", b'{"a": 1}')
    assert bus.poll(0.1) == ("transactions.raw", b'{"a": 1}')
    assert bus.poll(0.01) is None


def test_handle_message_persists_and_alerts(stream_env, demo_df):
    env = stream_env
    result = handle_message(
        _message(demo_df.iloc[0]),
        env["features"],
        env["scorer"],
        env["factory"],
        env["settings"],
    )
    assert 0.0 <= result.score <= 1.0

    with env["factory"]() as session:
        assert session.query(Transaction).count() == 1
        assert session.query(Alert).count() == 1


def test_duplicate_delivery_is_idempotent(stream_env, demo_df):
    env = stream_env
    message = _message(demo_df.iloc[0], transaction_id="dup-1")
    handle_message(message, env["features"], env["scorer"], env["factory"], env["settings"])
    handle_message(message, env["features"], env["scorer"], env["factory"], env["settings"])

    with env["factory"]() as session:
        assert session.query(Transaction).count() == 1
        assert session.query(Alert).count() == 1


def test_replay_publishes_bounded_stream(demo_df):
    bus = InMemoryBus()
    sent = replay(demo_df.head(3), bus, rate=0, topic="transactions.raw")
    assert sent == 3

    keys = []
    for _ in range(3):
        topic, value = bus.poll(0.1)
        assert topic == "transactions.raw"
        keys.append(json.loads(value)["card_id"])

    assert keys == list(demo_df.head(3)["card_id"])
