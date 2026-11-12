"""Minimal in-process latency metrics for the demo dashboard."""

from __future__ import annotations

import threading
from collections import deque


class Metrics:
    def __init__(self) -> None:
        self.count = 0
        self.latencies: deque[float] = deque(maxlen=2000)
        self._lock = threading.Lock()

    def observe(self, seconds: float) -> None:
        with self._lock:
            self.count += 1
            self.latencies.append(seconds)

    def _quantile(self, q: float) -> float:
        with self._lock:
            values = list(self.latencies)
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
        return ordered[index]

    def render(self) -> str:
        with self._lock:
            count = self.count
        lines = [
            "# HELP fraud_score_requests_total Total scoring requests",
            "# TYPE fraud_score_requests_total counter",
            f"fraud_score_requests_total {count}",
            "# HELP fraud_score_latency_seconds Recent scoring latency quantiles",
            "# TYPE fraud_score_latency_seconds gauge",
        ]
        for quantile in (0.5, 0.95, 0.99):
            line = (
                f'fraud_score_latency_seconds{{quantile="{quantile}"}} '
                f"{self._quantile(quantile):.6f}"
            )
            lines.append(line)
        return "\n".join(lines) + "\n"
