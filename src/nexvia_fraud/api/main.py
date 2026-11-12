"""HTTP API for scoring and case review."""

from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from nexvia_fraud.api.metrics import Metrics
from nexvia_fraud.api.schemas import (
    AlertDetail,
    AlertOut,
    BatchRequest,
    BatchResponse,
    DecisionRequest,
    ScoreRequest,
    ScoreResponse,
)
from nexvia_fraud.audit.chain import verify_audit
from nexvia_fraud.config import Settings
from nexvia_fraud.db.models import AuditLog, Transaction
from nexvia_fraud.db.repo import (
    count_prior_cases,
    decide,
    get_alert,
    list_alerts,
    list_audit,
    list_transactions,
)
from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.scorer import Scorer
from nexvia_fraud.scoring import score_transaction


def _transaction_payload(transaction: Transaction) -> dict:
    return {
        "transaction_id": transaction.id,
        "card_id": transaction.card_id,
        "event_time": transaction.event_time.isoformat(),
        "amount": transaction.amount,
        "score": transaction.score,
        "mode": transaction.mode,
        "model_version": transaction.model_version,
        "features": transaction.features,
    }


def create_app(
    settings: Settings,
    scorer: Scorer,
    features: FeatureService,
    session_factory,
) -> FastAPI:
    app = FastAPI(title="nexvia-fraud", version="0.1.0")
    metrics = Metrics()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model_version": scorer.model_version}

    @app.get("/transactions")
    def transactions(limit: int = Query(default=100, ge=1, le=500)) -> dict:
        with session_factory() as session:
            rows = list_transactions(session, limit)
            return {"transactions": [_transaction_payload(row) for row in rows]}

    @app.post("/score", response_model=ScoreResponse)
    def score(request: ScoreRequest) -> ScoreResponse:
        start = time.perf_counter()
        result = score_transaction(
            request.model_dump(),
            features,
            scorer,
            session_factory,
            settings.alert_threshold,
        )
        metrics.observe(time.perf_counter() - start)
        return ScoreResponse(
            transaction_id=request.transaction_id,
            score=result.score,
            mode=result.mode,
            model_version=result.model_version,
            top_features=result.top_features,
        )

    @app.post("/score/batch", response_model=BatchResponse)
    def score_batch(request: BatchRequest) -> BatchResponse:
        scores = [score(transaction) for transaction in request.transactions]
        return BatchResponse(scores=scores)

    @app.get("/alerts")
    def alerts(
        status: str | None = None,
        min_score: float | None = None,
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict:
        with session_factory() as session:
            rows = list_alerts(session, status, min_score, limit)
            return {"alerts": [AlertOut.model_validate(row).model_dump() for row in rows]}

    @app.get("/alerts/{alert_id}", response_model=AlertDetail)
    def alert_detail(alert_id: str) -> AlertDetail:
        with session_factory() as session:
            alert = get_alert(session, alert_id)
            if alert is None:
                raise HTTPException(status_code=404, detail="alert not found")
            transaction = session.get(Transaction, alert.transaction_id)
            if transaction is None:
                raise HTTPException(status_code=404, detail="transaction not found")
            return AlertDetail(
                alert=AlertOut.model_validate(alert),
                transaction=_transaction_payload(transaction),
                top_features=transaction.explanation or [],
                prior_cases=count_prior_cases(session, transaction.card_id, alert.id),
            )

    @app.post("/alerts/{alert_id}/decision")
    def decision(alert_id: str, request: DecisionRequest) -> dict:
        try:
            with session_factory() as session:
                decision_row = decide(
                    session, alert_id, request.decision, request.reason, request.analyst
                )
                alert = get_alert(session, alert_id)
                last_audit = session.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
                return {
                    "alert": AlertOut.model_validate(alert).model_dump(),
                    "decision_id": decision_row.id,
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

    @app.get("/metrics", response_class=PlainTextResponse)
    def prometheus_metrics() -> str:
        return metrics.render()

    return app
