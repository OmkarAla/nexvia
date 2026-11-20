"""Feast-backed feature provider with a local fallback for unknown events."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from feast import FeatureStore

from nexvia_fraud.features.feast_definitions import (
    ALL_FEATURES,
    TRANSACTION,
    build_transaction_view,
    views,
)


def transaction_refs() -> list[str]:
    return [f"transaction_features:{feature}" for feature in ALL_FEATURES]


class FeastFeatureMissing(Exception):
    pass


class FeastFeatureService:
    def __init__(self, repo_path: str | Path, fallback=None) -> None:
        self.store = FeatureStore(repo_path=str(repo_path))
        self.fallback = fallback

    def feature_names(self) -> list[str]:
        return list(ALL_FEATURES)

    def get_features(
        self,
        card_id: str,
        event_time: pd.Timestamp,
        amount: float,
        device_id: str,
        email_domain: str,
        addr_id: str,
        transaction_id: str | None = None,
    ) -> dict[str, float]:
        if transaction_id is not None:
            try:
                response = self.store.get_online_features(
                    features=transaction_refs(),
                    entity_rows=[{"transaction_id": transaction_id}],
                ).to_dict()
                values = {
                    feature: response.get(feature, [None])[0] for feature in ALL_FEATURES
                }
                if all(value is not None for value in values.values()):
                    return {feature: float(value) for feature, value in values.items()}
            except Exception:  # noqa: BLE001 - fall through to the local provider
                pass

        if self.fallback is not None:
            return self.fallback.get_features(
                card_id,
                event_time,
                amount,
                device_id,
                email_domain,
                addr_id,
                transaction_id=transaction_id,
            )
        raise FeastFeatureMissing(transaction_id or "unknown transaction")


def load_training_matrix(df: pd.DataFrame, repo_path: str | Path) -> pd.DataFrame:
    store = FeatureStore(repo_path=str(repo_path))
    entity_df = pd.DataFrame(
        {
            "transaction_id": df["transaction_id"].astype(str),
            "event_timestamp": pd.to_datetime(df["event_time"], utc=True),
        }
    )
    result = store.get_historical_features(
        entity_df=entity_df, features=transaction_refs()
    ).to_df()
    result = result.set_index("transaction_id")
    ordered = result.reindex(df["transaction_id"].astype(str))
    return ordered[ALL_FEATURES].reset_index(drop=True)


def apply_and_materialize(
    repo_path: str | Path, start: pd.Timestamp, end: pd.Timestamp
) -> None:
    store = FeatureStore(repo_path=str(repo_path))
    store.apply([TRANSACTION, *views, build_transaction_view()])
    store.materialize(start_date=start, end_date=end)
