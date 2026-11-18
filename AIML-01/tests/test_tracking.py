from nexvia_fraud.models.train import train_model


def test_training_logs_an_mlflow_run(tmp_path, demo_df, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///./mlruns.db")
    monkeypatch.setenv("NEXVIA_DISABLE_MLFLOW", "0")

    train_model(demo_df, str(tmp_path / "model"), run_id="tracking-test")

    assert (tmp_path / "mlruns.db").exists()
    logged = [path for path in tmp_path.rglob("model.json") if "artifacts" in path.parts]
    assert logged
