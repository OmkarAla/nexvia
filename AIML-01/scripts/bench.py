"""Measure /score latency against a running API.

Usage: python scripts/bench.py --url http://127.0.0.1:8000 --n 200
"""

from __future__ import annotations

import argparse
import statistics
import time

import httpx
import pandas as pd


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(quantile * (len(ordered) - 1)))))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the scoring endpoint")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--data", default="data/demo/transactions.csv")
    args = parser.parse_args()

    row = pd.read_csv(args.data).iloc[0]

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            httpx.get(f"{args.url}/health", timeout=2)
            break
        except httpx.HTTPError:
            time.sleep(0.5)
    else:
        raise SystemExit("API did not become ready within 30s")

    latencies: list[float] = []
    failures = 0
    with httpx.Client(timeout=10) as client:
        for index in range(args.n):
            payload = {
                "transaction_id": f"bench-{int(time.time() * 1000)}-{index}",
                "card_id": row.card_id,
                "event_time": pd.Timestamp(row.event_time).isoformat(),
                "amount": float(row.amount),
                "device_id": row.device_id,
                "email_domain": row.email_domain,
                "addr_id": row.addr_id,
            }
            start = time.perf_counter()
            response = client.post(f"{args.url}/score", json=payload)
            latencies.append((time.perf_counter() - start) * 1000)
            if response.status_code != 200:
                failures += 1

    print(f"requests: {args.n}, failures: {failures}")
    print(f"p50: {percentile(latencies, 0.50):.1f} ms")
    print(f"p95: {percentile(latencies, 0.95):.1f} ms")
    print(f"p99: {percentile(latencies, 0.99):.1f} ms")
    print(f"mean: {statistics.fmean(latencies):.1f} ms")
    print(f"sequential throughput: {1000 / statistics.fmean(latencies):.1f} req/s")


if __name__ == "__main__":
    main()
