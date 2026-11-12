"""Replay the demo dataset into Kafka at a bounded, demo-friendly rate."""

from __future__ import annotations

import argparse
import time

import pandas as pd

from nexvia_fraud.config import get_settings
from nexvia_fraud.streaming.bus import KafkaPublisher
from nexvia_fraud.streaming.producer import replay


def main() -> None:
    settings = get_settings()

    parser = argparse.ArgumentParser(description="Replay demo transactions into Kafka")
    parser.add_argument("--rate", type=float, default=settings.replay_rate)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--pause", type=float, default=5.0)
    args = parser.parse_args()

    frame = pd.read_csv(settings.demo_data_path)
    publisher = KafkaPublisher(settings.kafka_bootstrap)

    while True:
        sent = replay(
            frame,
            publisher,
            rate=args.rate,
            topic=settings.raw_topic,
            limit=args.limit,
        )
        publisher.flush()
        print(f"replayed {sent} transactions at {args.rate}/s", flush=True)
        if not args.loop:
            break
        time.sleep(args.pause)


if __name__ == "__main__":
    main()
