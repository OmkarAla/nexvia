from pathlib import Path

import yaml


def test_dvc_pipeline_declared():
    assert Path("dvc.yaml").exists()
    assert Path("dvc.lock").exists()

    pipeline = yaml.safe_load(Path("dvc.yaml").read_text())
    assert "demo_dicom" in pipeline["stages"]
    assert pipeline["stages"]["demo_dicom"]["outs"] == ["data/generated"]

    params = yaml.safe_load(Path("params.yaml").read_text())
    assert params["seed"] == 7
