"""Persistence for studies, decisions, audit, and the worker cursor."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from nexvia_imaging.audit.chain import GENESIS, append_audit
from nexvia_imaging.db.models import (
    AuditHead,
    AuditLog,
    Decision,
    Study,
    WorkerCursor,
    utcnow,
)


def init_db(engine) -> None:
    from nexvia_imaging.db.models import Base

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        if session.get(AuditHead, 1) is None:
            session.add(AuditHead(id=1, hash=GENESIS))
            session.commit()


def upsert_study(session: Session, payload: dict) -> Study:
    study = session.get(Study, payload["study_uid"])
    if study is None:
        study = Study(id=payload["study_uid"])
        session.add(study)

    study.modality = payload.get("modality", study.modality)
    study.description = payload.get("description", study.description)
    study.n_instances = int(payload.get("n_instances", study.n_instances or 0))
    study.status = payload.get("status", study.status)
    study.findings = payload.get("findings", study.findings or [])
    study.overlays = payload.get("overlays", study.overlays or [])
    study.model_version = payload.get("model_version", study.model_version)
    study.updated_at = utcnow()

    session.commit()
    session.refresh(study)
    return study


def list_studies(session: Session, status: str | None = None, limit: int = 100) -> list[Study]:
    query = select(Study).order_by(Study.updated_at.desc()).limit(limit)
    if status:
        query = query.where(Study.status == status)
    return list(session.scalars(query))


def get_study(session: Session, study_id: str) -> Study | None:
    return session.get(Study, study_id)


def decide(session: Session, study_id: str, decision: str, comment: str, reviewer: str) -> Decision:
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be 'approve' or 'reject'")
    if not comment.strip():
        raise ValueError("comment is required")
    if not reviewer.strip():
        raise ValueError("reviewer is required")

    study = session.get(Study, study_id)
    if study is None:
        raise ValueError("study not found")

    result = session.execute(
        update(Study)
        .where(Study.id == study_id, Study.status != "reviewed")
        .values(status="reviewed", updated_at=utcnow())
    )
    if result.rowcount != 1:
        raise ValueError("study already reviewed")

    row = Decision(
        id=uuid4().hex,
        study_id=study_id,
        decision=decision,
        comment=comment,
        reviewer=reviewer,
    )
    session.add(row)
    session.flush()
    append_audit(
        session,
        {
            "event": "review",
            "study_id": study_id,
            "decision": decision,
            "comment": comment,
            "reviewer": reviewer,
        },
        commit=False,
    )
    session.commit()
    session.refresh(row)
    return row


def list_audit(session: Session, limit: int = 200) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).order_by(AuditLog.id.asc()).limit(limit)))


def get_cursor(session: Session, key: str = "orthanc_changes") -> int:
    cursor = session.get(WorkerCursor, key)
    return cursor.value if cursor else 0


def set_cursor(session: Session, value: int, key: str = "orthanc_changes") -> None:
    cursor = session.get(WorkerCursor, key)
    if cursor is None:
        cursor = WorkerCursor(key=key, value=value)
        session.add(cursor)
    else:
        cursor.value = value
        cursor.updated_at = utcnow()
    session.commit()
