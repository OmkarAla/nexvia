"""Imaging review API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from nexvia_imaging.api.schemas import DecisionOut, DecisionRequest, StudyOut
from nexvia_imaging.audit.chain import verify_audit
from nexvia_imaging.db.models import AuditLog
from nexvia_imaging.db.repo import decide, get_study, list_audit, list_studies


def create_app(session_factory, overlay_dir: str | Path, model_version: str) -> FastAPI:
    app = FastAPI(title="nexvia-imaging", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    overlay_root = Path(overlay_dir)
    overlay_root.mkdir(parents=True, exist_ok=True)
    app.mount("/overlays", StaticFiles(directory=str(overlay_root)), name="overlays")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model_version": model_version}

    @app.get("/studies")
    def studies(
        status: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        with session_factory() as session:
            rows = list_studies(session, status, limit)
            return {"studies": [StudyOut.model_validate(row).model_dump() for row in rows]}

    @app.get("/studies/{study_id}")
    def study_detail(study_id: str) -> dict:
        with session_factory() as session:
            study = get_study(session, study_id)
            if study is None:
                raise HTTPException(status_code=404, detail="study not found")
            return {"study": StudyOut.model_validate(study).model_dump()}

    @app.post("/studies/{study_id}/decision")
    def study_decision(study_id: str, body: DecisionRequest) -> dict:
        try:
            with session_factory() as session:
                decision = decide(session, study_id, body.decision, body.comment, body.reviewer)
                study = get_study(session, study_id)
                last_audit = session.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
                return {
                    "study": StudyOut.model_validate(study).model_dump(),
                    "decision": DecisionOut.model_validate(decision).model_dump(),
                    "audit_hash": last_audit.hash if last_audit else "",
                }
        except ValueError as exc:
            message = str(exc)
            status_code = 404 if "not found" in message else 409
            raise HTTPException(status_code=status_code, detail=message) from exc

    @app.get("/audit")
    def audit() -> dict:
        with session_factory() as session:
            rows = list_audit(session)
            return {
                "entries": [
                    {
                        "id": row.id,
                        "prev_hash": row.prev_hash,
                        "hash": row.hash,
                        "payload": row.payload,
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in rows
                ],
                "valid": verify_audit(session),
            }

    return app
