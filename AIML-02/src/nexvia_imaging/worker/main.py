"""Poll Orthanc for stable studies and process them."""

from __future__ import annotations

import logging
from pathlib import Path

from nexvia_imaging.db.repo import get_cursor, set_cursor
from nexvia_imaging.worker.pipeline import process_study

logger = logging.getLogger(__name__)


def run_once(
    client,
    session_factory,
    classifier,
    overlay_dir: str | Path,
    segmenter=None,
) -> dict:
    with session_factory() as session:
        since = get_cursor(session)

    studies, last = client.stable_studies(since)
    processed = 0
    failures: list[dict] = []

    for study_uid in studies:
        try:
            process_study(
                study_uid,
                client,
                session_factory,
                classifier,
                overlay_dir,
                segmenter,
            )
            processed += 1
        except Exception as exc:  # noqa: BLE001 - one bad study must not stop the loop
            logger.exception("failed to process %s", study_uid)
            failures.append({"study_uid": study_uid, "error": str(exc)})

    with session_factory() as session:
        set_cursor(session, last)

    return {"processed": processed, "failures": failures, "cursor": last}
