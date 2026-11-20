"""Choose the feature provider from configuration."""

from __future__ import annotations

import logging

import pandas as pd

from nexvia_fraud.config import Settings
from nexvia_fraud.features.service import FeatureService

logger = logging.getLogger(__name__)


def build_feature_provider(settings: Settings, frame: pd.DataFrame):
    local = FeatureService.from_dataframe(frame)
    if settings.feature_backend != "feast":
        return local

    try:
        from nexvia_fraud.features.feast_service import FeastFeatureService

        return FeastFeatureService(settings.feast_repo_path, fallback=local)
    except Exception:  # noqa: BLE001 - serving must not depend on Feast being up
        logger.warning("Feast provider unavailable; using in-process features", exc_info=True)
        return local
