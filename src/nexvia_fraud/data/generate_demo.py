"""Deterministic synthetic transaction data with injected fraud rings.

The committed demo CSV is produced by this module. No real customer data is
used or redistributed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = [
    "transaction_id",
    "card_id",
    "event_time",
    "amount",
    "device_id",
    "email_domain",
    "addr_id",
    "is_fraud",
]

_SPAN = pd.Timedelta(days=30)


def _assign_rings(
    df: pd.DataFrame, rng: np.random.Generator, target_fraud_rate: float
) -> pd.DataFrame:
    """Overwrite shared entities for a subset of cards and mark them fraud."""
    counts = df.groupby("card_id").size().sort_values(ascending=False)
    target_rows = max(2, int(len(df) * target_fraud_rate))

    selected: list[str] = []
    rows = 0
    for card_id, count in counts.sample(frac=1.0, random_state=int(rng.integers(0, 2**31))).items():
        if rows >= target_rows:
            break
        selected.append(card_id)
        rows += int(count)

    df = df.copy()
    df["is_fraud"] = 0

    # Rings of 2-5 cards share a device, email domain and address.
    ring_size = int(rng.integers(2, 6))
    for index in range(0, len(selected), ring_size):
        ring_id = index // ring_size
        members = selected[index : index + ring_size]
        if not members:
            continue
        mask = df["card_id"].isin(members)
        df.loc[mask, "device_id"] = f"ring-device-{ring_id:02d}"
        df.loc[mask, "email_domain"] = f"ring{ring_id:02d}.example"
        df.loc[mask, "addr_id"] = f"ring-addr-{ring_id:02d}"
        df.loc[mask, "is_fraud"] = 1

    return df


def generate_demo_transactions(n: int = 5000, seed: int = 7) -> pd.DataFrame:
    """Return ``n`` synthetic transactions with a fraud-ring structure."""
    rng = np.random.default_rng(seed)
    n_cards = max(20, n // 8)
    card_index = rng.integers(0, n_cards, n)

    base = pd.Timestamp("2026-01-01T00:00:00Z")
    offsets = rng.uniform(0.0, _SPAN.total_seconds(), n)
    event_time = base + pd.to_timedelta(offsets, unit="s")

    amount = np.round(rng.lognormal(mean=3.4, sigma=0.9, size=n), 2)
    card_id = np.array([f"card-{i:04d}" for i in card_index])

    device = np.where(
        rng.random(n) < 0.2,
        np.char.add(np.char.add(card_id, "-secondary"), ""),
        np.char.add(card_id, "-primary"),
    )
    email_domain = np.array([f"{c.replace('card-', 'user')}.example" for c in card_id])
    addr_id = np.array([f"addr-{i % 200:03d}" for i in card_index])

    df = pd.DataFrame(
        {
            "card_id": card_id,
            "event_time": event_time,
            "amount": amount,
            "device_id": device,
            "email_domain": email_domain,
            "addr_id": addr_id,
        }
    )

    # Sort by time (globally) so each card's history is monotonic and ids are
    # assigned in event order.
    df = df.sort_values("event_time", kind="stable").reset_index(drop=True)
    df["transaction_id"] = [f"txn-{i:06d}" for i in range(len(df))]

    df = _assign_rings(df, rng, target_fraud_rate=0.05)

    df["is_fraud"] = df["is_fraud"].astype(int)
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
    return df[COLUMNS]


def write_demo_csv(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic fraud demo data")
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="data/demo/transactions.csv")
    args = parser.parse_args()

    df = generate_demo_transactions(args.n, args.seed)
    write_demo_csv(df, args.out)
    print(f"wrote {len(df)} transactions to {args.out} (fraud rate {df.is_fraud.mean():.3f})")


if __name__ == "__main__":
    main()
