"""Optional MLflow tracking for training runs.

The file store is the default so local training never needs a server. Set
``MLFLOW_TRACKING_URI`` to point at the Compose MLflow service.
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def log_training_run(
    run_id: str,
    params: dict,
    metrics: dict,
    artifacts: list[str | Path],
    experiment: str = "nexvia-fraud",
) -> bool:
    if os.getenv("NEXVIA_DISABLE_MLFLOW") == "1":
        return False
    try:
        import mlflow

        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///./mlruns.db")
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment)

        with mlflow.start_run(run_name=run_id):
            mlflow.set_tags({"run_id": run_id, "project": "nexvia-fraud"})
            mlflow.log_params({key: str(value)[:250] for key, value in params.items()})
            numeric = {
                key: float(value)
                for key, value in metrics.items()
                if isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
            }
            if numeric:
                mlflow.log_metrics(numeric)
            for artifact in artifacts:
                path = Path(artifact)
                if path.exists():
                    mlflow.log_artifact(str(path))
        return True
    except Exception:  # noqa: BLE001 - tracking must never break training
        logger.warning("MLflow logging skipped", exc_info=True)
        return False
