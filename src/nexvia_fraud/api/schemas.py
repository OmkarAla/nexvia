"""Request and response models for the fraud API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, field_serializer

from nexvia_fraud.timeutil import iso_utc


class ScoreRequest(BaseModel):
    transaction_id: str = Field(max_length=64)
    card_id: str = Field(max_length=64)
    event_time: AwareDatetime
    amount: float = Field(ge=0, allow_inf_nan=False)
    device_id: str = Field(default="unknown-device", max_length=128)
    email_domain: str = Field(default="unknown.example", max_length=128)
    addr_id: str = Field(default="unknown-addr", max_length=128)


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

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return iso_utc(value)


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=1, max_length=512)
    analyst: str = Field(min_length=1, max_length=128)


class AlertDetail(BaseModel):
    alert: AlertOut
    transaction: dict
    top_features: list[FeatureContribution]
    prior_cases: int
