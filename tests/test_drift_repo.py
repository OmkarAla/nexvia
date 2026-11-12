import pytest

from nexvia_fraud.db.models import DriftReport
from nexvia_fraud.db.repo import (
    create_retraining_request_if_absent,
    latest_drift_report,
    list_retraining_requests,
    resolve_retraining_request,
    save_drift_report,
)

SUMMARY = {
    "drift_share": 0.4,
    "dataset_drift": True,
    "n_reference": 100,
    "n_current": 60,
    "columns": [{"column": "amount_zscore", "p_value": 0.001, "drifted": True}],
    "method": "evidently:DataDriftPreset",
}


def test_save_and_read_latest(session):
    save_drift_report(session, {**SUMMARY, "drift_share": 0.1, "dataset_drift": False})
    second = save_drift_report(session, SUMMARY)

    assert latest_drift_report(session).id == second.id
    assert session.query(DriftReport).count() == 2


def test_only_one_open_request_per_episode(session):
    report = save_drift_report(session, SUMMARY)

    assert create_retraining_request_if_absent(session, report.id, "drift share 0.40") is not None
    assert create_retraining_request_if_absent(session, report.id, "drift share 0.42") is None
    assert len(list_retraining_requests(session)) == 1


def test_resolve_request(session):
    report = save_drift_report(session, SUMMARY)
    request = create_retraining_request_if_absent(session, report.id, "drift")

    resolved = resolve_retraining_request(session, request.id, "approved", "ana")

    assert resolved.status == "approved"
    assert resolved.resolved_by == "ana"
    assert resolved.resolved_at is not None


def test_resolve_twice_is_rejected(session):
    report = save_drift_report(session, SUMMARY)
    request = create_retraining_request_if_absent(session, report.id, "drift")
    resolve_retraining_request(session, request.id, "approved", "ana")

    with pytest.raises(ValueError):
        resolve_retraining_request(session, request.id, "rejected", "bob")


def test_resolve_rejects_unknown_status(session):
    report = save_drift_report(session, SUMMARY)
    request = create_retraining_request_if_absent(session, report.id, "drift")

    with pytest.raises(ValueError):
        resolve_retraining_request(session, request.id, "maybe", "ana")
