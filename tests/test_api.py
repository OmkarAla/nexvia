import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from nexvia_fraud.api.main import create_app
from nexvia_fraud.config import Settings
from nexvia_fraud.db.models import Base
from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.scorer import Scorer
from nexvia_fraud.models.train import train_model


@pytest.fixture(scope="module")
def api_model(demo_df, tmp_path_factory):
    out = tmp_path_factory.mktemp("api-model")
    train_model(demo_df, out, "api-test")
    return out


@pytest.fixture
def api_env(api_model, demo_df):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    settings = Settings(alert_threshold=0.0, model_dir=str(api_model))
    app = create_app(
        settings,
        Scorer.load(api_model),
        FeatureService.from_dataframe(demo_df),
        factory,
    )
    with TestClient(app) as test_client:
        yield {"client": test_client, "factory": factory}


@pytest.fixture
def client(api_env):
    return api_env["client"]


def _payload(row, transaction_id="api-txn-1"):
    return {
        "transaction_id": transaction_id,
        "card_id": row.card_id,
        "event_time": row.event_time.isoformat(),
        "amount": float(row.amount),
        "device_id": row.device_id,
        "email_domain": row.email_domain,
        "addr_id": row.addr_id,
    }


def test_health_reports_model_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_version": "api-test"}


def test_score_returns_contract(client, demo_df):
    response = client.post("/score", json=_payload(demo_df.iloc[0]))
    assert response.status_code == 200
    body = response.json()
    assert body["transaction_id"] == "api-txn-1"
    assert 0.0 <= body["score"] <= 1.0
    assert body["mode"] == "xgb_only"
    assert body["model_version"] == "api-test"
    assert len(body["top_features"]) > 0
    assert set(body["top_features"][0]) == {"feature", "value", "contribution"}


def test_batch_empty_returns_empty_list(client):
    response = client.post("/score/batch", json={"transactions": []})
    assert response.status_code == 200
    assert response.json() == {"scores": []}


def test_unknown_card_scores(client):
    body = {
        "transaction_id": "ghost-1",
        "card_id": "ghost-card",
        "event_time": "2026-01-01T00:00:00Z",
        "amount": 5.0,
        "device_id": "ghost-device",
        "email_domain": "ghost.example",
        "addr_id": "ghost-addr",
    }
    response = client.post("/score", json=body)
    assert response.status_code == 200
    assert 0.0 <= response.json()["score"] <= 1.0


def test_alert_lifecycle_and_audit(client, demo_df):
    client.post("/score", json=_payload(demo_df.iloc[0], transaction_id="lifecycle-1"))

    listing = client.get("/alerts", params={"status": "open"}).json()["alerts"]
    alert = next(item for item in listing if item["transaction_id"] == "lifecycle-1")

    detail = client.get(f"/alerts/{alert['id']}").json()
    assert detail["transaction"]["transaction_id"] == "lifecycle-1"
    assert len(detail["top_features"]) > 0
    assert detail["prior_cases"] == 0

    decision = client.post(
        f"/alerts/{alert['id']}/decision",
        json={"decision": "approve", "reason": "verified with customer", "analyst": "ana"},
    )
    assert decision.status_code == 200
    body = decision.json()
    assert body["alert"]["status"] == "approved"
    assert len(body["audit_hash"]) == 64

    second = client.post(
        f"/alerts/{alert['id']}/decision",
        json={"decision": "reject", "reason": "changed", "analyst": "bob"},
    )
    assert second.status_code == 409

    audit = client.get("/audit").json()
    assert audit["valid"] is True
    assert len(audit["entries"]) == 1


def test_decision_on_missing_alert_is_404(client):
    response = client.post(
        "/alerts/does-not-exist/decision",
        json={"decision": "approve", "reason": "x", "analyst": "ana"},
    )
    assert response.status_code == 404


def test_metrics_endpoint(client, demo_df):
    client.post("/score", json=_payload(demo_df.iloc[0], transaction_id="metrics-1"))
    text = client.get("/metrics").text
    assert "fraud_score_requests_total" in text
    assert 'fraud_score_latency_seconds{quantile="0.99"}' in text


def test_recent_transactions_endpoint(client, demo_df):
    client.post("/score", json=_payload(demo_df.iloc[0], transaction_id="feed-1"))
    body = client.get("/transactions").json()
    assert any(item["transaction_id"] == "feed-1" for item in body["transactions"])


def test_naive_event_time_is_422(client, demo_df):
    body = _payload(demo_df.iloc[0], transaction_id="naive-1")
    body["event_time"] = "2026-01-02T00:00:00"
    response = client.post("/score", json=body)
    assert response.status_code == 422


def test_non_finite_amount_is_rejected(client, demo_df):
    from pydantic import ValidationError

    from nexvia_fraud.api.schemas import ScoreRequest

    body = _payload(demo_df.iloc[0], transaction_id="inf-1")
    body["amount"] = float("inf")
    with pytest.raises(ValidationError):
        ScoreRequest(**body)


def test_timestamps_are_normalized_to_utc_z(client, demo_df):
    body = _payload(demo_df.iloc[0], transaction_id="tz-1")
    body["event_time"] = "2026-01-02T05:30:00+05:30"
    assert client.post("/score", json=body).status_code == 200

    listing = client.get("/transactions").json()["transactions"]
    stored = next(item for item in listing if item["transaction_id"] == "tz-1")
    assert stored["event_time"] == "2026-01-02T00:00:00Z"


DRIFT_SUMMARY = {
    "drift_share": 0.4,
    "dataset_drift": True,
    "n_reference": 3500,
    "n_current": 60,
    "columns": [{"column": "amount_zscore", "p_value": 0.001, "drifted": True}],
    "method": "evidently:DataDriftPreset",
}


def test_drift_endpoint_is_empty_before_first_run(client):
    assert client.get("/drift/latest").json() == {"report": None}


def test_drift_and_retraining_endpoints(api_env):
    from nexvia_fraud.db.repo import (
        create_retraining_request_if_absent,
        save_drift_report,
    )

    client = api_env["client"]
    with api_env["factory"]() as session:
        report = save_drift_report(session, DRIFT_SUMMARY)
        request = create_retraining_request_if_absent(session, report.id, "drift share 0.40")
        request_id = request.id

    latest = client.get("/drift/latest").json()["report"]
    assert latest["id"] == report.id
    assert latest["drift_share"] == 0.4
    assert latest["columns"][0]["column"] == "amount_zscore"

    requests = client.get("/retraining-requests").json()["requests"]
    assert len(requests) == 1
    assert requests[0]["status"] == "open"

    resolved = client.post(
        f"/retraining-requests/{request_id}/resolve",
        json={"status": "approved", "resolved_by": "ana"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["request"]["status"] == "approved"

    again = client.post(
        f"/retraining-requests/{request_id}/resolve",
        json={"status": "rejected", "resolved_by": "bob"},
    )
    assert again.status_code == 409


def test_resolve_missing_request_is_404(client):
    response = client.post(
        "/retraining-requests/nope/resolve",
        json={"status": "approved", "resolved_by": "ana"},
    )
    assert response.status_code == 404
