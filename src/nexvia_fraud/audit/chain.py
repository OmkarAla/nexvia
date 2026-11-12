"""Append-only hash chain used to make the audit log tamper-evident."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexvia_fraud.db.models import AuditLog

GENESIS = "0" * 64


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def append_audit(session: Session, payload: dict, commit: bool = True) -> AuditLog:
    last = session.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
    prev_hash = last.hash if last is not None else GENESIS
    digest = hashlib.sha256((prev_hash + canonical(payload)).encode()).hexdigest()

    row = AuditLog(prev_hash=prev_hash, payload=payload, hash=digest)
    session.add(row)
    if commit:
        session.commit()
        session.refresh(row)
    else:
        session.flush()
    return row


def verify_audit(session: Session) -> bool:
    prev_hash = GENESIS
    for row in session.scalars(select(AuditLog).order_by(AuditLog.id.asc())):
        if row.prev_hash != prev_hash:
            return False
        expected = hashlib.sha256((prev_hash + canonical(row.payload)).encode()).hexdigest()
        if row.hash != expected:
            return False
        prev_hash = row.hash
    return True
