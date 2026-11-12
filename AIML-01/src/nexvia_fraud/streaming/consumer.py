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


def consume_one(
    consumer: Consumer,
    features: FeatureService,
    scorer: Scorer,
    session_factory,
    settings: Settings,
) -> bool:
    """Process at most one message.

    Returns True when a message was handled. Malformed JSON is committed and
    skipped (poison pill); processing failures propagate *without* committing,
    so a restarted consumer replays the message instead of losing it.
    """
    item = consumer.poll(1.0)
    if item is None:
        return False

    _topic, value = item
    try:
        raw = json.loads(value)
    except json.JSONDecodeError:
        logger.exception("malformed message; committing and skipping")
        consumer.commit()
        return True

    handle_message(raw, features, scorer, session_factory, settings)
    consumer.commit()
    return True


def run(
    consumer: Consumer,
    features: FeatureService,
    scorer: Scorer,
    session_factory,
    settings: Settings,
) -> None:
    while True:
        consume_one(consumer, features, scorer, session_factory, settings)
