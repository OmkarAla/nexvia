import numpy as np
import pandas as pd
import pytest

from nexvia_fraud.db.models import DriftReport, Transaction
from nexvia_fraud.db.repo import (
    list_retraining_requests,
    upsert_transaction,
)
from nexvia_fraud.drift.job import run_drift_check
from nexvia_fraud.features.service import FEATURE_NAMES


@pytest.fixture
def reference_path(tmp_path):
    rng = np.random.default_rng(3)
    reference = pd.DataFrame(
        {name: rng.normal(0, 1, 300) for name in FEATURE_NAMES}
    )
    path = tmp_path / "reference_features.parquet"
    reference.to_parquet(path, index=False)
    return str(path), reference


def _seed(session, reference: pd.DataFrame, rows: int, shift_columns: int = 0):
    frame = reference.head(rows).copy()
    if shift_columns:
        for name in FEATURE_NAMES[:shift_columns]:
            frame[name] = frame[name] + 10.0
    for index, row in frame.iterrows():
        upsert_transaction(
            session,
            {
                "transaction_id": f"drift-{index}",
                "card_id": f"card-{index}",
                "event_time": "2026-01-01T00:00:00Z",
                "amount": 10.0,
                "score": 0.1,
                "features": row.to_dict(),
                "mode": "xgb_only",
                "model_version": "test",
            },
        )
    session.commit()


def test_insufficient_data_does_not_report(session, reference_path):
    path, reference = reference_path
    _seed(session, reference, rows=5)

    result = run_drift_check(session, path, threshold=0.1, min_rows=50)

    assert result["status"] == "insufficient_data"
    assert result["n_current"] == 5
    assert session.query(DriftReport).count() == 0


def test_identical_distribution_creates_no_request(session, reference_path):
    path, reference = reference_path
    _seed(session, reference, rows=100)

    result = run_drift_check(session, path, threshold=0.5, min_rows=50)

    assert result["status"] == "ok"
    assert result["drift_share"] == 0.0
    assert result["request_id"] is None
    assert session.query(DriftReport).count() == 1
    assert list_retraining_requests(session) == []


def test_shifted_distribution_creates_one_request(session, reference_path):
    path, reference = reference_path
    _seed(session, reference, rows=100, shift_columns=6)

    first = run_drift_check(session, path, threshold=0.1, min_rows=50)
    second = run_drift_check(session, path, threshold=0.1, min_rows=50)

    assert first["status"] == "ok"
    assert first["drift_share"] > 0.1
    assert first["request_id"] is not None
    assert second["request_id"] is None
    assert len(list_retraining_requests(session)) == 1
    assert session.query(Transaction).count() == 100


def test_missing_reference_is_explicit(session, tmp_path):
    result = run_drift_check(
        lambda: session, str(tmp_path / "nope.parquet"), threshold=0.1, min_rows=50
    )

    assert result["status"] == "reference_missing"
