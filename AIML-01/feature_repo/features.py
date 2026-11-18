"""Feast feature definitions mirroring the fraud FeatureService.

The same 13 features are grouped into the four views from the design. The
offline table is produced by `scripts/build_feast_features.py`; the online
store is SQLite locally and Redis in Compose.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from feast import Entity, FeatureView, Field, FileSource, ValueType
from feast.types import Float32

CARD = Entity(name="card", join_keys=["card_id"], value_type=ValueType.STRING)

FEATURE_GROUPS = {
    "txn_velocity": ["velocity_1h", "velocity_24h", "unique_devices_24h"],
    "amount_profile": ["amount_mean", "amount_std", "amount_zscore"],
    "entity_change": [
        "device_change",
        "email_change",
        "addr_change",
        "seconds_since_last_txn",
    ],
    "card_graph_stats": [
        "device_share_count",
        "email_share_count",
        "addr_share_count",
    ],
}

DEFAULT_SOURCE = "../data/features/transaction_features.parquet"


def build_views(source_path: str | Path = DEFAULT_SOURCE) -> list[FeatureView]:
    source = FileSource(path=str(source_path), timestamp_field="event_timestamp")
    return [
        FeatureView(
            name=name,
            entities=[CARD],
            ttl=timedelta(days=90),
            schema=[Field(name=feature, dtype=Float32) for feature in features],
            source=source,
        )
        for name, features in FEATURE_GROUPS.items()
    ]


views = build_views()
