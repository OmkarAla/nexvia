"""Train a real-data IEEE-CIS model with the raw competition features.

This is separate from the 13-feature demo model. It reports the real-data
numbers while the demo artifacts stay synthetic and fast.
"""

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

START = pd.Timestamp("2017-11-30T00:00:00Z")

CATEGORICALS = [
    "ProductCD",
    "card4",
    "card6",
    "P_emaildomain",
    "R_emaildomain",
    "DeviceInfo",
    "M4",
    "M5",
    "M6",
]
IDENTITY_COLUMNS = ["TransactionID", "DeviceInfo"]


def load_raw(data_dir: str | Path, limit: int = 30000, seed: int = 7) -> pd.DataFrame:
    data_dir = Path(data_dir)
    transactions = pd.read_csv(data_dir / "train_transaction.csv")
    identity = pd.read_csv(data_dir / "train_identity.csv", usecols=IDENTITY_COLUMNS)
    merged = transactions.merge(identity, on="TransactionID", how="left")

    merged["event_time"] = START + pd.to_timedelta(merged["TransactionDT"], unit="s")
    merged["transaction_id"] = merged["TransactionID"].astype(str)
    merged["is_fraud"] = merged["isFraud"].astype(int)

    if limit is not None and limit < len(merged):
        merged = merged.sample(n=limit, random_state=seed)

    return merged.sort_values("event_time").reset_index(drop=True)


def prepare_matrix(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series, list[str]]:
    excluded = {
        "TransactionID",
        "TransactionDT",
        "isFraud",
        "transaction_id",
        "event_time",
        "is_fraud",
    }
    frame = frame.copy()

    for column in CATEGORICALS:
        if column not in frame.columns:
            frame[column] = "missing"
        frame[column] = frame[column].fillna("missing").astype(str)
        frame[column] = pd.factorize(frame[column])[0]

    feature_columns = [
        column
        for column in frame.columns
        if column not in excluded
        and pd.api.types.is_numeric_dtype(frame[column])
    ]
    matrix = frame[feature_columns].replace([np.inf, -np.inf], np.nan)

    usable = [column for column in matrix.columns if matrix[column].notna().any()]
    matrix = matrix[usable]

    return matrix, frame["is_fraud"], frame["event_time"], usable


def _precision_at_1pct_fpr(y_true: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    fpr, _tpr, thresholds = roc_curve(y_true, scores)
    index = max(0, int(np.searchsorted(fpr, 0.01, side="right")) - 1)
    threshold = thresholds[index]
    predicted = scores >= threshold
    return (
        float(precision_score(y_true, predicted, zero_division=0)),
        float(recall_score(y_true, predicted, zero_division=0)),
    )


def train_ieee(
    data_path: str | Path,
    out_dir: str | Path,
    run_id: str = "ieee-raw-001",
) -> dict:
    frame = pd.read_parquet(data_path)
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
    matrix, labels, times, feature_names = prepare_matrix(frame)

    split = times.quantile(0.8)
    validation_split = times.quantile(0.7)
    train_mask = (times < validation_split).to_numpy()
    val_mask = ((times >= validation_split) & (times < split)).to_numpy()
    test_mask = (times >= split).to_numpy()

    X_train, y_train = matrix[train_mask], labels[train_mask]
    X_val, y_val = matrix[val_mask], labels[val_mask]
    X_test, y_test = matrix[test_mask], labels[test_mask]

    positives = int(y_train.sum())
    negatives = int(len(y_train) - positives)
    model = XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=negatives / positives,
        eval_metric="aucpr",
        early_stopping_rounds=40,
        tree_method="hist",
        random_state=7,
        n_jobs=4,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    scores = model.predict_proba(X_test)[:, 1]
    pr_auc = float(average_precision_score(y_test, scores))
    roc_auc = float(roc_auc_score(y_test, scores)) if len(set(y_test)) > 1 else float("nan")
    precision_1pct, recall_1pct = _precision_at_1pct_fpr(y_test, scores)
    top = np.argsort(-scores)[:100]
    precision_at_100 = float(np.mean(y_test.to_numpy()[top])) if len(top) else 0.0

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.get_booster().save_model(str(out / "model.json"))
    (out / "feature_names.json").write_text(json.dumps(feature_names, indent=2))
    pd.DataFrame(X_train, columns=feature_names).head(5000).to_parquet(
        out / "reference_features.parquet", index=False
    )

    metrics = {
        "run_id": run_id,
        "model_version": run_id,
        "dataset": "IEEE-CIS Fraud Detection (30k row sample of 590,540)",
        "n_train": int(train_mask.sum()),
        "n_validation": int(val_mask.sum()),
        "n_test": int(test_mask.sum()),
        "n_features": len(feature_names),
        "pr_auc": pr_auc,
        "roc_auc": roc_auc,
        "precision_at_1pct_fpr": precision_1pct,
        "recall_at_1pct_fpr": recall_1pct,
        "precision_at_100": precision_at_100,
        "prevalence_test": float(y_test.mean()),
        "best_iteration": int(getattr(model, "best_iteration", -1) or -1),
        "test_start": str(pd.Timestamp(split).isoformat()),
        "validation_start": str(pd.Timestamp(validation_split).isoformat()),
    }
    for key, value in metrics.items():
        if isinstance(value, float) and not math.isfinite(value):
            metrics[key] = None
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    reports = Path("reports")
    reports.mkdir(exist_ok=True)
    (reports / "ieee_metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train on raw IEEE-CIS features")
    parser.add_argument("--data", default="data/ieee/raw_30k.parquet")
    parser.add_argument("--out", default="artifacts/ieee")
    parser.add_argument("--run-id", default="ieee-raw-001")
    args = parser.parse_args()
    print(json.dumps(train_ieee(args.data, args.out, args.run_id), indent=2))


if __name__ == "__main__":
    main()
