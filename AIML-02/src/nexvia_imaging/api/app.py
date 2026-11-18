"""ASGI entry point for the imaging API."""

from __future__ import annotations

from nexvia_imaging.api.main import create_app
from nexvia_imaging.config import get_settings
from nexvia_imaging.db.engine import make_engine, make_session_factory
from nexvia_imaging.db.repo import init_db
from nexvia_imaging.models.classifier import DenseNetClassifier


def build_app():
    settings = get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)

    try:
        model_version = DenseNetClassifier(settings.model_dir).model_version
    except FileNotFoundError:
        model_version = "no-checkpoint"

    return create_app(
        session_factory,
        overlay_dir="data/overlays",
        model_version=model_version,
    )


app = build_app()
