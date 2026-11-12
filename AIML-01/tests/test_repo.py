import pytest

from nexvia_fraud.db.models import Alert, Transaction
from nexvia_fraud.db.repo import (
    create_alert_if_absent,
    decide,
    get_alert,
    list_alerts,
    upsert_transaction,
)

PAYLOAD = {
    "transaction_id": "t1",
    "card_id": "c1",
    "event_time": "2026-01-01T00:00:00Z",
    "amount": 10.0,
    "score": 0.2,
    "mode": "xgb_only",
    "model_version": "demo-001",
    "features": {"velocity_1h": 0.0},
}


@pytest.fixture
def alert(session):
    upsert_transaction(session, PAYLOAD)
    created = create_alert_if_absent(session, "t1", 0.9)
    assert created is not None
    return created


def test_upsert_is_idempotent(session):
    upsert_transaction(session, PAYLOAD)
    upsert_transaction(session, PAYLOAD)
    assert session.query(Transaction).count() == 1


def test_upsert_updates_score_on_replay(session):
    upsert_transaction(session, PAYLOAD)
    upsert_transaction(session, {**PAYLOAD, "score": 0.95})
    stored = session.get(Transaction, "t1")
    assert stored.score == 0.95
    assert session.query(Transaction).count() == 1


def test_one_alert_per_transaction(session, alert):
    assert create_alert_if_absent(session, "t1", 0.9) is None
    assert session.query(Alert).count() == 1


def test_second_decision_rejected(session, alert):
    decide(session, alert.id, "approve", "looks fine", "ana")
    with pytest.raises(ValueError):
        decide(session, alert.id, "reject", "changed my mind", "bob")


def test_decision_updates_status(session, alert):
    decision = decide(session, alert.id, "reject", "ring member", "ana")
    stored = get_alert(session, alert.id)
    assert decision.decision == "reject"
    assert stored.status == "rejected"
    assert stored.reason == "ring member"


def test_list_alerts_filters(session, alert):
    assert len(list_alerts(session, None, None, 50)) == 1
    assert len(list_alerts(session, "open", None, 50)) == 1
    assert len(list_alerts(session, "approved", None, 50)) == 0
    assert len(list_alerts(session, None, 0.95, 50)) == 0


def test_event_time_is_normalized_to_utc(session):
    transaction = upsert_transaction(
        session, {**PAYLOAD, "transaction_id": "tz-1", "event_time": "2026-01-02T05:30:00+05:30"}
    )
    assert transaction.event_time.replace(tzinfo=None).isoformat() == "2026-01-02T00:00:00"
