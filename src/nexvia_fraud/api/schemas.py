"""Request and response models for the fraud API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    transaction_id: str
    card_id: str
    event_time: datetime
    amount: float = Field(ge=0)
    device_id: str = "unknown-device"
    email_domain: str = "unknown.example"
    addr_id: str = "unknown-addr"


class FeatureContribution(BaseModel):
    feature: str
    value: float
    contribution: float


class ScoreResponse(BaseModel):
    transaction_id: str
    score: float
    mode: str
    model_version: str
    top_features: list[FeatureContribution]


class BatchRequest(BaseModel):
    transactions: list[ScoreRequest]


class BatchResponse(BaseModel):
    scores: list[ScoreResponse]


class AlertOut(BaseModel):
    id: str
    transaction_id: str
    score: float
    status: str
    reason: str | None = None
    assignee: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str
    analyst: str


class AlertDetail(BaseModel):
    alert: AlertOut
    transaction: dict
    top_features: list[FeatureContribution]
    prior_cases: int
