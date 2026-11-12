"""Persistence operations used by the API, the consumer, and the seed script."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nexvia_fraud.audit.chain import append_audit
from nexvia_fraud.db.models import Alert, AuditLog, Decision, Transaction, utcnow


def init_db(engine) -> None:
    from nexvia_fraud.db.models import Base

    Base.metadata.create_all(engine)


def _as_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def upsert_transaction(session: Session, payload: dict) -> Transaction:
    transaction_id = payload["transaction_id"]
    transaction = session.get(Transaction, transaction_id)
    if transaction is None:
        transaction = Transaction(
            id=transaction_id,
            card_id=payload["card_id"],
            event_time=_as_datetime(payload["event_time"]),
            amount=float(payload["amount"]),
            features=payload.get("features") or {},
            explanation=payload.get("top_features") or [],
            score=float(payload["score"]),
            mode=payload.get("mode", "xgb_only"),
            model_version=payload.get("model_version", "unknown"),
        )
        session.add(transaction)
    else:
        transaction.score = float(payload["score"])
        transaction.mode = payload.get("mode", transaction.mode)
        transaction.model_version = payload.get("model_version", transaction.model_version)
        transaction.features = payload.get("features") or transaction.features
        transaction.explanation = payload.get("top_features") or transaction.explanation
    session.commit()
    session.refresh(transaction)
    return transaction


def create_alert_if_absent(session: Session, transaction_id: str, score: float) -> Alert | None:
    existing = session.scalar(select(Alert).where(Alert.transaction_id == transaction_id))
    if existing is not None:
        return None

    alert = Alert(
        id=uuid4().hex,
        transaction_id=transaction_id,
        score=float(score),
        status="open",
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


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

    alert = session.get(Alert, alert_id, with_for_update=True)
    if alert is None:
        raise ValueError("alert not found")
    if alert.status != "open":
        raise ValueError("alert already decided")

    alert.status = "approved" if decision == "approve" else "rejected"
    alert.reason = reason
    alert.assignee = analyst
    alert.updated_at = utcnow()

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
