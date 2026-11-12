"""Replay historical transactions into Kafka at a bounded rate."""

from __future__ import annotations

import json
import time

import pandas as pd

from nexvia_fraud.streaming.bus import Publisher


def replay(
    df: pd.DataFrame,
    publisher: Publisher,
    rate: float,
    topic: str = "transactions.raw",
    limit: int | None = None,
) -> int:
    sent = 0
    delay = 1.0 / rate if rate > 0 else 0.0

    for row in df.itertuples(index=False):
        payload = {
            "transaction_id": row.transaction_id,
            "card_id": row.card_id,
            "event_time": pd.Timestamp(row.event_time).isoformat(),
            "amount": float(row.amount),
            "device_id": row.device_id,
            "email_domain": row.email_domain,
            "addr_id": row.addr_id,
        }
        publisher.publish(topic, key=str(row.card_id), value=json.dumps(payload).encode())
        sent += 1

        if limit is not None and sent >= limit:
            break
        if delay:
            time.sleep(delay)

    return sent
