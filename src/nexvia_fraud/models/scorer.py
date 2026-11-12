"""Load a trained booster and score transactions with TreeSHAP contributions."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import xgboost as xgb


@dataclass
class ScoreResult:
    score: float
    top_features: list[dict] = field(default_factory=list)
    mode: str = "xgb_only"
    model_version: str = ""


class Scorer:
    def __init__(
        self,
        booster: xgb.Booster,
        feature_names: list[str],
        model_version: str,
        best_iteration: int = -1,
    ) -> None:
        self._booster = booster
        self.feature_names = feature_names
        self.model_version = model_version
        self.best_iteration = best_iteration

    @classmethod
    def load(cls, model_dir: str | Path) -> Scorer:
        model_dir = Path(model_dir)
        booster = xgb.Booster()
        booster.load_model(str(model_dir / "model.json"))
        feature_names = json.loads((model_dir / "feature_names.json").read_text())

        metrics_path = model_dir / "metrics.json"
        version = "unknown"
        best_iteration = -1
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text())
            version = metrics.get("model_version") or metrics.get("run_id") or "unknown"
            best_iteration = int(metrics.get("best_iteration", -1))

        return cls(booster, feature_names, version, best_iteration)

    def _iteration_range(self) -> tuple[int, int] | None:
        if self.best_iteration >= 0:
            return (0, self.best_iteration + 1)
        return None

    def score(self, features: dict[str, float]) -> ScoreResult:
        values = np.asarray(
            [[self._sanitize(features.get(name, 0.0)) for name in self.feature_names]],
            dtype=np.float32,
        )
        matrix = xgb.DMatrix(values)
        iteration_range = self._iteration_range()
        probability = float(self._booster.predict(matrix, iteration_range=iteration_range)[0])
        contributions = self._booster.predict(
            matrix, pred_contribs=True, iteration_range=iteration_range
        )[0]

        items = [
            {
                "feature": name,
                "value": float(value),
                "contribution": float(contribution),
            }
            for name, value, contribution in zip(
                self.feature_names, values[0], contributions[:-1], strict=False
            )
        ]
        items.sort(key=lambda item: abs(item["contribution"]), reverse=True)

        return ScoreResult(
            score=probability,
            top_features=items[:10],
            mode="xgb_only",
            model_version=self.model_version,
        )

    @staticmethod
    def _sanitize(value: float) -> float:
        value = float(value)
        return value if math.isfinite(value) else 0.0
