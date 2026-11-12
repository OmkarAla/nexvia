import json

import pandas as pd

from nexvia_fraud.models.gnn import train_gnn


def test_train_gnn_writes_artifacts(tmp_path, demo_df):
    metrics = train_gnn(demo_df, str(tmp_path), run_id="gnn-test", epochs=5)

    assert (tmp_path / "gnn_model.pt").exists()

    scores = pd.read_parquet(tmp_path / "gnn_card_scores.parquet")
    assert set(scores.columns) == {"card_id", "gnn_score", "split"}
    assert scores["gnn_score"].between(0.0, 1.0).all()
    assert scores["card_id"].nunique() == demo_df["card_id"].nunique()

    stored = json.loads((tmp_path / "gnn_metrics.json").read_text())
    assert 0.0 <= stored["pr_auc"] <= 1.0
    assert 0.0 <= stored["roc_auc"] <= 1.0
    assert stored["run_id"] == "gnn-test"
    assert stored["epochs_run"] <= 5
    assert stored == metrics
