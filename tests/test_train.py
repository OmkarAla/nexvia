import json

import pandas as pd

from nexvia_fraud.features.service import FeatureService
from nexvia_fraud.models.train import train_model


def test_training_writes_artifacts_and_metrics(tmp_path, demo_df):
    metrics = train_model(demo_df, str(tmp_path), run_id="test-run")

    assert 0.0 <= metrics["pr_auc"] <= 1.0
    assert metrics["pr_auc"] > 0.5
    assert metrics["run_id"] == "test-run"
    assert (tmp_path / "model.json").exists()
    assert (tmp_path / "metrics.json").exists()

    names = json.loads((tmp_path / "feature_names.json").read_text())
    assert names == FeatureService.from_dataframe(demo_df).feature_names()


def test_split_is_temporal(tmp_path, demo_df):
    metrics = train_model(demo_df, str(tmp_path), run_id="t")
    assert metrics["n_train"] + metrics["n_test"] == len(demo_df)

    split = pd.Timestamp(metrics["test_start"])
    train_max = demo_df[demo_df.event_time < split].event_time.max()
    test_min = demo_df[demo_df.event_time >= split].event_time.min()
    assert train_max < test_min


def test_training_accepts_csv_string_timestamps(tmp_path, demo_df):
    csv_path = tmp_path / "demo.csv"
    demo_df.to_csv(csv_path, index=False)
    frame = pd.read_csv(csv_path)

    metrics = train_model(frame, str(tmp_path / "artifacts"), run_id="csv-run")

    assert metrics["pr_auc"] > 0.5
