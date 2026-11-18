"""Worker entry point: poll Orthanc and process stable studies."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from nexvia_imaging.config import get_settings
from nexvia_imaging.db.engine import make_engine, make_session_factory
from nexvia_imaging.db.repo import init_db
from nexvia_imaging.dicom.client import OrthancClient
from nexvia_imaging.models.classifier import DenseNetClassifier
from nexvia_imaging.worker.main import run_once


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)

    client = OrthancClient(settings.orthanc_url, settings.orthanc_user, settings.orthanc_password)
    classifier = DenseNetClassifier(settings.model_dir)
    overlay_dir = Path("data/overlays")

    while True:
        result = run_once(client, session_factory, classifier, overlay_dir)
        print(result, flush=True)
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
