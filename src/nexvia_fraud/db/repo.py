"""Persistence operations used by the API, the consumer, and the seed script."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from nexvia_fraud.audit.chain import GENESIS, append_audit
from nexvia_fraud.db.models import (
    Alert,
    AuditHead,
    AuditLog,
    Decision,
    DriftReport,
    RetrainingRequest,
    Transaction,
    utcnow,
)
from nexvia_fraud.timeutil import to_utc

_UPSERT_COLUMNS = (
    "card_id",
    "event_time",
    "amount",
    "features",
    "explanation",
    "score",
    "mode",
    "model_version",
)


def _insert_for(session: Session, model):
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        return insert(model)
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        return insert(model)
    raise NotImplementedError(f"upsert not implemented for dialect {dialect}")


def init_db(engine) -> None:
    from nexvia_fraud.db.models import Base

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.get(AuditHead, 1) is None:
            session.add(AuditHead(id=1, hash=GENESIS))
            session.commit()


def upsert_transaction(session: Session, payload: dict) -> Transaction:
    values = {
        "id": payload["transaction_id"],
        "card_id": payload["card_id"],
        "event_time": to_utc(payload["event_time"]),
        "amount": float(payload["amount"]),
        "features": payload.get("features") or {},
        "explanation": payload.get("top_features") or [],
        "score": float(payload["score"]),
        "mode": payload.get("mode", "xgb_only"),
        "model_version": payload.get("model_version", "unknown"),
    }
    statement = _insert_for(session, Transaction).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=["id"],
        set_={name: getattr(statement.excluded, name) for name in _UPSERT_COLUMNS},
    )
    session.execute(statement)
    return session.get(Transaction, payload["transaction_id"], populate_existing=True)


def create_alert_if_absent(session: Session, transaction_id: str, score: float) -> Alert | None:
    statement = (
        _insert_for(session, Alert)
        .values(
            id=uuid4().hex,
            transaction_id=transaction_id,
            score=float(score),
            status="open",
        )
        .on_conflict_do_nothing(index_elements=["transaction_id"])
    )
    result = session.execute(statement)
    if result.rowcount == 0:
        return None
    return session.scalar(select(Alert).where(Alert.transaction_id == transaction_id))


def list_alerts(
    session: Session,
    status: str | None = None,
    min_score: float | None = None,
    limit: int = 50,
) -> list[Alert]:
    query = select(Alert).order_by(Alert.score.desc(), Alert.created_at.desc())
    if status is not None:
        query = query.where(Alert.status == status)
    if min_score is not None:
        query = query.where(Alert.score >= min_score)
    query = query.limit(limit)
    return list(session.scalars(query))


def get_alert(session: Session, alert_id: str) -> Alert | None:
    return session.get(Alert, alert_id)


def count_prior_cases(session: Session, card_id: str, exclude_alert_id: str) -> int:
    query = (
        select(func.count())
        .select_from(Alert)
        .join(Transaction, Alert.transaction_id == Transaction.id)
        .where(Transaction.card_id == card_id, Alert.id != exclude_alert_id)
    )
    return int(session.scalar(query) or 0)


def decide(session: Session, alert_id: str, decision: str, reason: str, analyst: str) -> Decision:
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be 'approve' or 'reject'")
    if not reason.strip():
        raise ValueError("reason is required")
    if not analyst.strip():
        raise ValueError("analyst is required")

    alert = session.get(Alert, alert_id)
    if alert is None:
        raise ValueError("alert not found")

    status = "approved" if decision == "approve" else "rejected"
    result = session.execute(
        update(Alert)
        .where(Alert.id == alert_id, Alert.status == "open")
        .values(status=status, reason=reason, assignee=analyst, updated_at=utcnow())
    )
    if result.rowcount != 1:
        raise ValueError("alert already decided")

    row = Decision(
        id=uuid4().hex,
        alert_id=alert_id,
        decision=decision,
        reason=reason,
        analyst=analyst,
    )
    session.add(row)
    session.flush()

    append_audit(
        session,
        {
            "event": "decision",
            "alert_id": alert_id,
            "decision": decision,
            "reason": reason,
            "analyst": analyst,
        },
        commit=False,
    )
    session.commit()
    session.refresh(row)
    return row


def list_audit(session: Session, limit: int = 200) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).order_by(AuditLog.id.asc()).limit(limit)))


def list_transactions(session: Session, limit: int = 100) -> list[Transaction]:
    query = select(Transaction).order_by(Transaction.event_time.desc()).limit(limit)
    return list(session.scalars(query))


def save_drift_report(session: Session, summary: dict) -> DriftReport:
    report = DriftReport(
        id=uuid4().hex,
        drift_share=float(summary["drift_share"]),
        dataset_drift=bool(summary["dataset_drift"]),
        n_reference=int(summary["n_reference"]),
        n_current=int(summary["n_current"]),
        summary=summary,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def latest_drift_report(session: Session) -> DriftReport | None:
    query = select(DriftReport).order_by(DriftReport.seq.desc()).limit(1)
    return session.scalar(query)


def create_retraining_request_if_absent(
    session: Session, drift_report_id: str, reason: str
) -> RetrainingRequest | None:
    existing = session.scalar(
        select(RetrainingRequest).where(RetrainingRequest.status == "open").limit(1)
    )
    if existing is not None:
        return None

    request = RetrainingRequest(
        id=uuid4().hex,
        drift_report_id=drift_report_id,
        reason=reason,
        status="open",
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def list_retraining_requests(session: Session, limit: int = 50) -> list[RetrainingRequest]:
    query = select(RetrainingRequest).order_by(RetrainingRequest.seq.desc()).limit(limit)
    return list(session.scalars(query))


def resolve_retraining_request(
    session: Session, request_id: str, status: str, resolved_by: str
) -> RetrainingRequest:
    if status not in {"approved", "rejected"}:
        raise ValueError("status must be 'approved' or 'rejected'")
    request = session.scalar(select(RetrainingRequest).where(RetrainingRequest.id == request_id))
    if request is None:
        raise ValueError("request not found")
    if request.status != "open":
        raise ValueError("request already resolved")

    request.status = status
    request.resolved_by = resolved_by
    request.resolved_at = utcnow()
    session.commit()
    session.refresh(request)
    return request
