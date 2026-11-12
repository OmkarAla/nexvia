"""Point-in-time feature computation over transaction history.

The vertical slice keeps history in memory. The depth phase replaces this
implementation with Feast while preserving the same interface and semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

FEATURE_NAMES = [
    "velocity_1h",
    "velocity_24h",
    "unique_devices_24h",
    "amount_mean",
    "amount_std",
    "amount_zscore",
    "device_change",
    "email_change",
    "addr_change",
    "seconds_since_last_txn",
    "device_share_count",
    "email_share_count",
    "addr_share_count",
]

_HOUR_NS = 3_600_000_000_000
_DAY_NS = 24 * _HOUR_NS


@dataclass
class _CardHistory:
    times: np.ndarray
    amounts: np.ndarray
    devices: np.ndarray
    emails: np.ndarray
    addrs: np.ndarray


class FeatureService:
    def __init__(
        self,
        history: dict[str, _CardHistory],
        entity_index: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]],
    ) -> None:
        self._history = history
        self._entity_index = entity_index

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> FeatureService:
        frame = df.copy()
        frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
        frame = frame.sort_values(["card_id", "event_time"], kind="stable")

        history: dict[str, _CardHistory] = {}
        for card_id, group in frame.groupby("card_id", sort=False):
            history[str(card_id)] = _CardHistory(
                times=group["event_time"].astype("datetime64[ns, UTC]").astype("int64").to_numpy(),
                amounts=group["amount"].astype(float).to_numpy(),
                devices=group["device_id"].astype(str).to_numpy(),
                emails=group["email_domain"].astype(str).to_numpy(),
                addrs=group["addr_id"].astype(str).to_numpy(),
            )

        entity_index: dict[str, dict[str, tuple[np.ndarray, np.ndarray]]] = {}
        for column in ("device_id", "email_domain", "addr_id"):
            index: dict[str, tuple[np.ndarray, np.ndarray]] = {}
            ordered = frame.sort_values("event_time", kind="stable")
            for value, group in ordered.groupby(column, sort=False):
                index[str(value)] = (
                    group["event_time"].astype("datetime64[ns, UTC]").astype("int64").to_numpy(),
                    group["card_id"].astype(str).to_numpy(),
                )
            entity_index[column] = index

        return cls(history, entity_index)

    def _share_count(self, column: str, value: str, t: int) -> float:
        entry = self._entity_index[column].get(value)
        if entry is None:
            return 0.0
        times, cards = entry
        cutoff = int(np.searchsorted(times, t, side="left"))
        if cutoff == 0:
            return 0.0
        return float(len(set(cards[:cutoff].tolist())))


    def feature_names(self) -> list[str]:
        return list(FEATURE_NAMES)

    def get_features(
        self,
        card_id: str,
        event_time: pd.Timestamp,
        amount: float,
        device_id: str,
        email_domain: str,
        addr_id: str,
    ) -> dict[str, float]:
        ts = pd.Timestamp(event_time)
        if ts.tzinfo is None:
            raise ValueError("event_time must be timezone-aware (UTC)")
        t = int(ts.value)

        empty = {name: 0.0 for name in FEATURE_NAMES}
        empty["seconds_since_last_txn"] = -1.0

        shares = {
            "device_share_count": self._share_count("device_id", device_id, t),
            "email_share_count": self._share_count("email_domain", email_domain, t),
            "addr_share_count": self._share_count("addr_id", addr_id, t),
        }

        history = self._history.get(card_id)
        if history is None or len(history.times) == 0:
            return {**empty, **shares}

        cutoff = int(np.searchsorted(history.times, t, side="left"))
        if cutoff == 0:
            return {**empty, **shares}

        times = history.times[:cutoff]
        amounts = history.amounts[:cutoff]

        start_1h = int(np.searchsorted(times, t - _HOUR_NS, side="left"))
        start_24h = int(np.searchsorted(times, t - _DAY_NS, side="left"))

        mean = float(np.mean(amounts))
        std = float(np.std(amounts))
        zscore = float((amount - mean) / std) if std > 0 else 0.0

        last = cutoff - 1
        return {
            "velocity_1h": float(cutoff - start_1h),
            "velocity_24h": float(cutoff - start_24h),
            "unique_devices_24h": float(len(set(history.devices[start_24h:cutoff].tolist()))),
            "amount_mean": mean,
            "amount_std": std,
            "amount_zscore": zscore,
            "device_change": float(device_id != history.devices[last]),
            "email_change": float(email_domain != history.emails[last]),
            "addr_change": float(addr_id != history.addrs[last]),
            "seconds_since_last_txn": float((t - int(times[last])) / 1e9),
            **shares,
        }
