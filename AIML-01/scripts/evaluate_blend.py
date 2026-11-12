"""Evaluate XGBoost, GNN, and blended scores on the held-out test window."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.blend import apply_blender
from nexvia_fraud.models.gnn import score_cards_before
from nexvia_fraud.models.scorer import Scorer


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the blend on the test window")
    parser.add_argument("--data", default="data/demo/transactions.csv")
    parser.add_argument("--model-dir", default="artifacts/demo")
    parser.add_argument("--out", default="reports/blend_evaluation.json")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    metrics = json.loads((model_dir / "metrics.json").read_text())
    test_start = pd.Timestamp(metrics["test_start"])

    frame = pd.read_csv(args.data)
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
    test = frame[frame["event_time"] >= test_start]

    service = FeatureService.from_dataframe(frame)
    scorer = Scorer.load(model_dir)

    past_scores = score_cards_before(model_dir, frame[frame["event_time"] < test_start])

    y: list[int] = []
    xgb: list[float] = []
    gnn: list[float] = []
    blended: list[float] = []

    for row in test.itertuples(index=False):
        card_score = past_scores.get(row.card_id)
        if card_score is None or scorer.blend is None:
            continue
        features = service.get_features(
            row.card_id,
            row.event_time,
            float(row.amount),
            row.device_id,
            row.email_domain,
            row.addr_id,
        )
        xgb_score = scorer.score(features, card_id=None).score
        xgb.append(xgb_score)
        gnn.append(card_score)
        blended.append(apply_blender(scorer.blend, xgb_score, card_score))
        y.append(int(row.is_fraud))

    y_array = np.asarray(y)

    def block(probabilities: list[float]) -> dict:
        values = np.asarray(probabilities)
        return {
            "pr_auc": float(average_precision_score(y_array, values)),
            "roc_auc": (
                float(roc_auc_score(y_array, values)) if len(np.unique(y_array)) > 1 else 0.0
            ),
        }

    result = {
        "n_test_rows": int(len(test)),
        "n_rows_with_gnn": int(len(y)),
        "prevalence": float(y_array.mean()) if len(y_array) else 0.0,
        "xgb_only": block(xgb),
        "gnn_only": block(gnn),
        "blended": block(blended),
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
