from nexvia_fraud.audit.chain import append_audit, verify_audit
from nexvia_fraud.db.models import AuditLog


def test_empty_chain_is_valid(session):
    assert verify_audit(session)


def test_chain_links_and_verifies(session):
    first = append_audit(session, {"action": "open", "id": 1})
    second = append_audit(session, {"action": "close", "id": 1})

    assert second.prev_hash == first.hash
    assert verify_audit(session)


def test_tamper_is_detected(session):
    append_audit(session, {"action": "open", "id": 1})
    append_audit(session, {"action": "close", "id": 1})

    row = session.query(AuditLog).first()
    row.payload = {"action": "tampered", "id": 1}
    session.commit()

    assert not verify_audit(session)


def test_head_tracks_tail(session):
    from nexvia_fraud.db.models import AuditHead

    append_audit(session, {"action": "open", "id": 1})
    last = append_audit(session, {"action": "close", "id": 1})
    head = session.get(AuditHead, 1)
    assert head is not None
    assert head.hash == last.hash


def test_truncation_is_detected(session):
    append_audit(session, {"action": "open", "id": 1})
    append_audit(session, {"action": "close", "id": 1})

    row = session.query(AuditLog).order_by(AuditLog.id.desc()).first()
    session.delete(row)
    session.commit()

    assert not verify_audit(session)
