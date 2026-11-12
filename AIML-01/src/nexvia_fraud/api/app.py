"""ASGI entry point: build the app from environment configuration."""

from __future__ import annotations

import pandas as pd

from nexvia_fraud.api.main import create_app
from nexvia_fraud.config import get_settings
from nexvia_fraud.db.engine import make_engine, make_session_factory
from nexvia_fraud.db.repo import init_db
from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.scorer import Scorer


def build_app():
    settings = get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)

    frame = pd.read_csv(settings.demo_data_path)
    features = FeatureService.from_dataframe(frame)
    scorer = Scorer.load(settings.model_dir)

    return create_app(settings, scorer, features, session_factory)


app = build_app()
