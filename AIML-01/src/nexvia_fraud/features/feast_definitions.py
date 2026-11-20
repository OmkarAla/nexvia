"""Feast feature definitions mirroring the fraud FeatureService.

The card-scoped views match the design. A transaction-scoped view is added so
serving can look up the exact feature row for a replayed event without
reading a future card state.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from feast import Entity, FeatureView, Field, FileSource, ValueType
from feast.types import Float32

CARD = Entity(name="card", join_keys=["card_id"], value_type=ValueType.STRING)
TRANSACTION = Entity(
    name="transaction", join_keys=["transaction_id"], value_type=ValueType.STRING
)

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

ALL_FEATURES = [feature for features in FEATURE_GROUPS.values() for feature in features]

DEFAULT_SOURCE = "../data/features/transaction_features.parquet"


def _source(source_path: str | Path) -> FileSource:
    return FileSource(path=str(source_path), timestamp_field="event_timestamp")


def build_views(source_path: str | Path = DEFAULT_SOURCE) -> list[FeatureView]:
    source = _source(source_path)
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


def build_transaction_view(source_path: str | Path = DEFAULT_SOURCE) -> FeatureView:
    return FeatureView(
        name="transaction_features",
        entities=[TRANSACTION],
        ttl=timedelta(days=3650),
        schema=[Field(name=feature, dtype=Float32) for feature in ALL_FEATURES],
        source=_source(source_path),
    )


views = build_views()
transaction_view = build_transaction_view()
