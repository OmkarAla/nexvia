import json

import numpy as np

from nexvia_fraud.models.blend import apply_blender, fit_blender
from nexvia_fraud.models.gnn import train_gnn
from nexvia_fraud.models.train import train_model


def test_fit_blender_learns_positive_weights():
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    xgb = np.array([0.05, 0.1, 0.2, 0.3, 0.7, 0.8, 0.9, 0.95])
    gnn = np.array([0.1, 0.15, 0.2, 0.35, 0.65, 0.75, 0.85, 0.9])

    blend = fit_blender(xgb, gnn, y)

    assert len(blend["coef"]) == 2
    assert blend["n"] == 8
    assert all(np.isfinite(value) for value in blend["coef"])
    assert all(value > 0 for value in blend["coef"])


def test_apply_blender_stays_a_probability():
    blend = {"coef": [1.2, 0.8], "intercept": -0.1, "n": 10}
    for xgb, gnn in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.5, 0.5)):
        probability = apply_blender(blend, xgb, gnn)
        assert 0.0 <= probability <= 1.0


def test_train_gnn_writes_blend_when_reference_model_exists(tmp_path, demo_df):
    train_model(demo_df, str(tmp_path), run_id="xgb-test")
    train_gnn(demo_df, str(tmp_path), run_id="gnn-test", epochs=5)

    blend = json.loads((tmp_path / "blend.json").read_text())

    assert len(blend["coef"]) == 2
    assert blend["n"] > 0
    assert 0.0 <= blend["xgb_val_pr_auc"] <= 1.0
