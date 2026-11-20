"""Scheduled drift check: compare live features to the training reference."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from nexvia_fraud.db.repo import (
    create_retraining_request_if_absent,
    list_transactions,
    save_drift_report,
)
from nexvia_fraud.drift.monitor import compute_drift

MAX_CURRENT_ROWS = 500


def run_drift_check(
    session: Session,
    reference_path: str,
    threshold: float,
    min_rows: int = 50,
) -> dict:
    path = Path(reference_path)
    if not path.exists():
        return {"status": "reference_missing", "reference_path": str(path)}

    reference = pd.read_parquet(path)
    columns = list(reference.columns)

    records = [row.features for row in list_transactions(session, MAX_CURRENT_ROWS)]
    records = [record for record in records if record]
    if not records:
        return {"status": "insufficient_data", "n_current": 0}

    current = pd.DataFrame(records)
    for column in columns:
        if column not in current.columns:
            current[column] = 0.0
    current = current[columns].astype(float).fillna(0.0)

    if len(current) < min_rows:
        return {"status": "insufficient_data", "n_current": int(len(current))}

    summary = compute_drift(reference, current, threshold)
    report = save_drift_report(session, summary)

    request = None
    if summary["drift_share"] >= threshold:
        request = create_retraining_request_if_absent(
            session,
            report.id,
            f"automatic drift trigger: share {summary['drift_share']:.2f} >= {threshold:.2f}",
        )

    return {
        "status": "ok",
        "report_id": report.id,
        "request_id": request.id if request is not None else None,
        **summary,
    }
