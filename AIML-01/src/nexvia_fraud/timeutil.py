"""UTC normalization helpers used at the API and persistence boundaries."""

from __future__ import annotations

from datetime import UTC, datetime


def to_utc(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        moment = value
    else:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def iso_utc(value: datetime | str) -> str:
    return to_utc(value).isoformat().replace("+00:00", "Z")
