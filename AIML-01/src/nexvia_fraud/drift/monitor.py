"""Evidently-based drift computation over the model's numeric features."""

from __future__ import annotations

import numpy as np
import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset

METHOD = "evidently:DataDriftPreset"


def compute_drift(reference: pd.DataFrame, current: pd.DataFrame, threshold: float = 0.3) -> dict:
    columns = list(reference.columns)
    definition = DataDefinition(numerical_columns=columns)

    report = Report([DataDriftPreset()])
    with np.errstate(invalid="ignore", divide="ignore"):
        snapshot = report.run(
            reference_data=Dataset.from_pandas(reference, data_definition=definition),
            current_data=Dataset.from_pandas(current, data_definition=definition),
        )
    payload = snapshot.dict()

    drift_share = 0.0
    per_column: list[dict] = []
    for metric in payload.get("metrics", []):
        config = metric.get("config", {})
        metric_type = str(config.get("type", ""))
        if metric_type.endswith("DriftedColumnsCount"):
            drift_share = float(metric["value"]["share"])
        elif metric_type.endswith("ValueDrift"):
            # Evidently picks the method from the window size: p-value tests
            # for small windows (drifted when p < threshold) and distance
            # metrics for larger ones (drifted when distance > threshold).
            score = float(metric["value"])
            method = str(config.get("method", ""))
            column_threshold = float(config.get("threshold", 0.1))
            is_p_value = "p_value" in method or "p-value" in method
            drifted = score < column_threshold if is_p_value else score > column_threshold
            per_column.append(
                {
                    "column": str(config.get("column")),
                    "score": score,
                    "method": method,
                    "drifted": drifted,
                }
            )

    return {
        "drift_share": drift_share,
        "dataset_drift": drift_share >= threshold,
        "n_reference": int(len(reference)),
        "n_current": int(len(current)),
        "columns": per_column,
        "method": METHOD,
    }
