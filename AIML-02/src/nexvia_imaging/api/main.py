"""Imaging review API."""

from __future__ import annotations

import json
from pathlib import Path

import pydicom
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from nexvia_imaging.api.schemas import DecisionOut, DecisionRequest, StudyOut
from nexvia_imaging.audit.chain import verify_audit
from nexvia_imaging.db.models import AuditLog
from nexvia_imaging.db.repo import decide, get_study, list_audit, list_studies


def _demo_index(demo_dir: Path) -> list[dict]:
    manifest_path = demo_dir / "manifest.json"
    if not manifest_path.exists():
        return []
    manifest = json.loads(manifest_path.read_text())
    studies = []
    for entry in manifest.get("studies", []):
        directory = demo_dir / entry["path"]
        files = sorted(directory.glob("*.dcm"))
        if not files:
            continue
        first = pydicom.dcmread(files[0])
        studies.append(
            {
                "study_uid": str(first.StudyInstanceUID),
                "modality": str(first.Modality),
                "description": str(getattr(first, "StudyDescription", "")),
                "image_urls": [f"/demo-dicom/{entry['path']}/{file.name}" for file in files],
            }
        )
    return studies


def create_app(
    session_factory,
    overlay_dir: str | Path,
    model_version: str,
    demo_dir: str | Path | None = None,
) -> FastAPI:
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

    demo_studies: list[dict] = []
    demo_files: dict[str, Path] = {}
    if demo_dir is not None and Path(demo_dir).exists():
        demo_studies = _demo_index(Path(demo_dir))
        app.mount("/demo-dicom", StaticFiles(directory=str(demo_dir)), name="demo-dicom")
        for entry in demo_studies:
            if entry["image_urls"]:
                relative = entry["image_urls"][len(entry["image_urls"]) // 2]
                demo_files[entry["study_uid"]] = Path(demo_dir) / relative.replace(
                    "/demo-dicom/", ""
                )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model_version": model_version}

    @app.get("/demo/studies")
    def demo_study_index() -> dict:
        return {"studies": demo_studies}

    @app.get("/studies/{study_id}/preview")
    def study_preview(study_id: str):
        """Rendered middle-slice PNG, used when DICOMweb is unavailable."""
        import io

        import pydicom
        from fastapi.responses import Response

        from nexvia_imaging.worker.pipeline import to_display_image

        path = demo_files.get(study_id)
        if path is None or not path.exists():
            raise HTTPException(status_code=404, detail="preview not available")
        image = to_display_image(pydicom.dcmread(path))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return Response(content=buffer.getvalue(), media_type="image/png")

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
