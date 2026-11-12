"""Shared scoring path used by both the HTTP API and the Kafka consumer."""

from __future__ import annotations

import pandas as pd

from nexvia_fraud.db.repo import create_alert_if_absent, upsert_transaction
from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.scorer import Scorer, ScoreResult


def score_transaction(
    payload: dict,
    features: FeatureService,
    scorer: Scorer,
    session_factory,
    threshold: float,
) -> ScoreResult:
    feature_values = features.get_features(
        payload["card_id"],
        pd.Timestamp(payload["event_time"]),
        float(payload["amount"]),
        payload.get("device_id", "unknown-device"),
        payload.get("email_domain", "unknown.example"),
        payload.get("addr_id", "unknown-addr"),
    )
    result = scorer.score(feature_values)

    record = {
        **payload,
        "features": feature_values,
        "score": result.score,
        "mode": result.mode,
        "model_version": result.model_version,
        "top_features": result.top_features,
    }

    with session_factory() as session:
        upsert_transaction(session, record)
        if result.score >= threshold:
            create_alert_if_absent(session, payload["transaction_id"], result.score)

    return result
