"""Train the demo XGBoost fraud model with honest, PR-based metrics."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from xgboost import XGBClassifier

from nexvia_fraud.config import Settings
from nexvia_fraud.features.service import FeatureService

TEST_FRACTION = 0.2


def _build_matrix(df: pd.DataFrame, service: FeatureService) -> np.ndarray:
    names = service.feature_names()
    rows = [
        [
            service.get_features(
                row.card_id,
                row.event_time,
                float(row.amount),
                row.device_id,
                row.email_domain,
                row.addr_id,
            )[name]
            for name in names
        ]
        for row in df.itertuples(index=False)
    ]
    return np.asarray(rows, dtype=np.float32)


def _precision_at_1pct_fpr(y_true: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    fpr, _tpr, thresholds = roc_curve(y_true, scores)
    idx = max(0, int(np.searchsorted(fpr, 0.01, side="right")) - 1)
    threshold = thresholds[idx]
    predicted = scores >= threshold
    return (
        float(precision_score(y_true, predicted, zero_division=0)),
        float(recall_score(y_true, predicted, zero_division=0)),
    )


def train_model(df: pd.DataFrame, out_dir: str | Path, run_id: str) -> dict:
    frame = df.copy()
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
    frame = frame.sort_values("event_time", kind="stable").reset_index(drop=True)
    service = FeatureService.from_dataframe(frame)
    features = service.feature_names()

    split = frame["event_time"].quantile(1 - TEST_FRACTION)
    train_mask = (frame["event_time"] < split).to_numpy()
    test_mask = ~train_mask
    if not train_mask.any() or not test_mask.any():
        raise ValueError("time split produced an empty side")

    X = _build_matrix(frame, service)
    y = frame["is_fraud"].to_numpy().astype(int)

    X_train, y_train = X[train_mask], y[train_mask]
    X_test, y_test = X[test_mask], y[test_mask]
    positives = int(y_train.sum())
    negatives = int(len(y_train) - positives)
    if positives == 0:
        raise ValueError("training window has no fraud examples")

    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        scale_pos_weight=(negatives / positives) if positives else 1.0,
        eval_metric="aucpr",
        early_stopping_rounds=30,
        tree_method="hist",
        random_state=7,
        n_jobs=2,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    scores = model.predict_proba(X_test)[:, 1]
    pr_auc = float(average_precision_score(y_test, scores))
    roc_auc = float(roc_auc_score(y_test, scores)) if len(set(y_test)) > 1 else float("nan")
    precision_1pct, recall_1pct = _precision_at_1pct_fpr(y_test, scores)

    top = np.argsort(-scores)[:100]
    precision_at_100 = float(np.mean(y_test[top])) if len(top) else 0.0

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.get_booster().save_model(str(out / "model.json"))
    (out / "feature_names.json").write_text(json.dumps(features, indent=2))

    metrics = {
        "run_id": run_id,
        "model_version": run_id,
        "pr_auc": pr_auc,
        "roc_auc": roc_auc,
        "precision_at_1pct_fpr": precision_1pct,
        "recall_at_1pct_fpr": recall_1pct,
        "precision_at_100": precision_at_100,
        "n_train": int(train_mask.sum()),
        "n_test": int(test_mask.sum()),
        "n_fraud_train": positives,
        "n_fraud_test": int(y_test.sum()),
        "prevalence_test": float(y_test.mean()) if len(y_test) else 0.0,
        "best_iteration": int(getattr(model, "best_iteration", -1) or -1),
        "test_start": str(pd.Timestamp(split).isoformat()),
        "feature_names": features,
    }
    for key, value in metrics.items():
        if isinstance(value, float) and not math.isfinite(value):
            metrics[key] = None

    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))

    if Path(out).resolve() == Path(Settings().model_dir).resolve():
        reports = Path("reports")
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "metrics.json").write_text(json.dumps(metrics, indent=2))

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the demo fraud model")
    parser.add_argument("--data", default="data/demo/transactions.csv")
    parser.add_argument("--out", default="artifacts/demo")
    parser.add_argument("--run-id", default="demo-001")
    args = parser.parse_args()

    df = pd.read_csv(args.data)
    metrics = train_model(df, args.out, args.run_id)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
