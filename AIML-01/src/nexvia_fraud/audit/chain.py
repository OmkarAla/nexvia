"""Append-only hash chain used to make the audit log tamper-evident."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexvia_fraud.db.models import AuditHead, AuditLog

GENESIS = "0" * 64


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def append_audit(session: Session, payload: dict, commit: bool = True) -> AuditLog:
    head = session.get(AuditHead, 1, with_for_update=True)
    if head is None:
        session.add(AuditHead(id=1, hash=GENESIS))
        session.flush()
        head = session.get(AuditHead, 1, with_for_update=True)

    prev_hash = head.hash
    digest = hashlib.sha256((prev_hash + canonical(payload)).encode()).hexdigest()

    row = AuditLog(prev_hash=prev_hash, payload=payload, hash=digest)
    session.add(row)
    head.hash = digest

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

    head = session.get(AuditHead, 1)
    if head is not None and head.hash != prev_hash:
        return False
    return True
