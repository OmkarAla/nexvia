"""Consume raw transactions, score them, and commit after a successful write."""

from __future__ import annotations

import json
import logging

from nexvia_fraud.config import Settings
from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.scorer import Scorer, ScoreResult
from nexvia_fraud.scoring import score_transaction
from nexvia_fraud.streaming.bus import Consumer

logger = logging.getLogger(__name__)


def handle_message(
    raw: dict,
    features: FeatureService,
    scorer: Scorer,
    session_factory,
    settings: Settings,
) -> ScoreResult:
    return score_transaction(raw, features, scorer, session_factory, settings.alert_threshold)


def run(
    consumer: Consumer,
    features: FeatureService,
    scorer: Scorer,
    session_factory,
    settings: Settings,
) -> None:
    while True:
        item = consumer.poll(1.0)
        if item is None:
            continue

        _topic, value = item
        try:
            raw = json.loads(value)
            handle_message(raw, features, scorer, session_factory, settings)
        except Exception:
            logger.exception("failed to process message; committing to avoid a poison-pill loop")
        consumer.commit()
