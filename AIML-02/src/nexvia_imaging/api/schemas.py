"""HTTP schemas for the imaging API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

from nexvia_imaging.timeutil import iso_utc


class FindingOut(BaseModel):
    label: str
    probability: float


class StudyOut(BaseModel):
    id: str
    modality: str
    description: str
    n_instances: int
    status: str
    findings: list[FindingOut]
    overlays: list[str]
    model_version: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at")
    def _serialize(self, value: datetime) -> str:
        return iso_utc(value)


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    comment: str = Field(min_length=1, max_length=1024)
    reviewer: str = Field(min_length=1, max_length=128)


class DecisionOut(BaseModel):
    id: str
    study_id: str
    decision: str
    comment: str
    reviewer: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _serialize_created(self, value: datetime) -> str:
        return iso_utc(value)
