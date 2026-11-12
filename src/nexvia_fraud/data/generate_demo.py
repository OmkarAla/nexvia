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
_EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "proton.me"]


def _assign_rings(
    df: pd.DataFrame, rng: np.random.Generator, target_fraud_rate: float
) -> pd.DataFrame:
    """Overwrite shared entities for a subset of cards and mark them fraud.

    Fraud rings are deliberately not perfectly separable: members sometimes
    fall back to their own devices (evasion), legitimate transactions share
    the same public devices and email domains, and a small amount of label
    noise is injected.
    """
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

    normal_device = df.groupby("card_id")["device_id"].agg(lambda s: s.mode().iloc[0])
    normal_email = df.groupby("card_id")["email_domain"].agg(lambda s: s.mode().iloc[0])
    normal_addr = df.groupby("card_id")["addr_id"].agg(lambda s: s.mode().iloc[0])

    # Rings of 2-5 cards share a device, email domain and address. The device
    # and address pools overlap with legitimate shared usage on purpose.
    ring_size = int(rng.integers(2, 6))
    ring_ids: list[int] = []
    for index in range(0, len(selected), ring_size):
        ring_id = index // ring_size
        members = selected[index : index + ring_size]
        if not members:
            continue
        ring_ids.append(ring_id)
        mask = df["card_id"].isin(members)
        df.loc[mask, "device_id"] = f"shared-device-{ring_id % 50:02d}"
        df.loc[mask, "email_domain"] = _EMAIL_DOMAINS[ring_id % len(_EMAIL_DOMAINS)]
        df.loc[mask, "addr_id"] = f"addr-{ring_id % 200:03d}"
        df.loc[mask, "is_fraud"] = 1

    if not ring_ids:
        return df

    # Evasion: a third of ring transactions use the card's own entities again.
    fraud_mask = df["is_fraud"] == 1
    revert = fraud_mask & (rng.random(len(df)) < 0.35)
    df.loc[revert, "device_id"] = df.loc[revert, "card_id"].map(normal_device)
    df.loc[revert, "email_domain"] = df.loc[revert, "card_id"].map(normal_email)
    df.loc[revert, "addr_id"] = df.loc[revert, "card_id"].map(normal_addr)

    # False positives: 6% of legitimate transactions land on a shared entity.
    legit = ~df["is_fraud"].astype(bool).to_numpy()
    shared = legit & (rng.random(len(df)) < 0.06)
    chosen = rng.choice(np.asarray(ring_ids), size=int(shared.sum()))
    df.loc[shared, "device_id"] = [f"shared-device-{r % 50:02d}" for r in chosen]
    df.loc[shared, "email_domain"] = [_EMAIL_DOMAINS[r % len(_EMAIL_DOMAINS)] for r in chosen]

    # Label noise: 1% of all rows are mislabeled.
    flip = rng.random(len(df)) < 0.01
    df.loc[flip, "is_fraud"] = 1 - df.loc[flip, "is_fraud"]

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

    shared_rows = rng.random(n) < 0.25
    device = np.where(
        shared_rows,
        [f"shared-device-{i % 50:02d}" for i in card_index],
        np.where(
            rng.random(n) < 0.2,
            np.array([f"{c}-secondary" for c in card_id]),
            np.array([f"{c}-primary" for c in card_id]),
        ),
    )
    card_domain = {
        i: _EMAIL_DOMAINS[int(rng.integers(0, len(_EMAIL_DOMAINS)))] for i in range(n_cards)
    }
    email_domain = np.array([card_domain[i] for i in card_index])
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
