import math

import pytest

from nexvia_fraud.models.scorer import Scorer
from nexvia_fraud.models.train import train_model


@pytest.fixture(scope="module")
def scorer(demo_df, tmp_path_factory):
    out = tmp_path_factory.mktemp("model")
    train_model(demo_df, out, "test-model")
    return Scorer.load(out)


def test_score_shape_and_top_k(scorer):
    features = {name: 0.0 for name in scorer.feature_names}
    features["amount_zscore"] = 2.0

    result = scorer.score(features)

    assert 0.0 <= result.score <= 1.0
    assert result.mode == "xgb_only"
    assert result.model_version == "test-model"
    assert 0 < len(result.top_features) <= 10
    assert len(result.top_features) == len({item["feature"] for item in result.top_features})
    for item in result.top_features:
        assert item["value"] == features[item["feature"]]


def test_missing_feature_is_finite(scorer):
    result = scorer.score({"velocity_1h": 1.0})
    assert math.isfinite(result.score)


def test_top_features_are_ranked_by_absolute_contribution(scorer):
    result = scorer.score({name: 1.0 for name in scorer.feature_names})
    magnitudes = [abs(item["contribution"]) for item in result.top_features]
    assert magnitudes == sorted(magnitudes, reverse=True)


def test_scoring_is_deterministic(scorer):
    features = {name: 0.5 for name in scorer.feature_names}
    first = scorer.score(features)
    second = scorer.score(features)
    assert first.score == second.score
    assert first.top_features == second.top_features


def test_scorer_uses_best_iteration(scorer):
    import numpy as np
    import xgboost as xgb

    assert scorer.best_iteration >= 0
    features = {name: 0.5 for name in scorer.feature_names}
    values = np.asarray([[features[name] for name in scorer.feature_names]], dtype=np.float32)
    expected = float(
        scorer._booster.predict(
            xgb.DMatrix(values), iteration_range=(0, scorer.best_iteration + 1)
        )[0]
    )
    assert scorer.score(features).score == pytest.approx(expected)


def test_scorer_blends_known_card(tmp_path, demo_df):
    import json

    import pandas as pd

    train_model(demo_df, str(tmp_path), run_id="blend-test")
    pd.DataFrame(
        [{"card_id": "card-known", "gnn_score": 0.9, "split": "train"}]
    ).to_parquet(tmp_path / "gnn_card_scores.parquet", index=False)
    (tmp_path / "blend.json").write_text(
        json.dumps({"coef": [0.7, 0.3], "intercept": 0.1, "n": 100})
    )

    scorer = Scorer.load(tmp_path)
    features = {name: 0.5 for name in scorer.feature_names}

    blended = scorer.score(features, card_id="card-known")
    assert blended.mode == "blended"
    assert blended.gnn_score == 0.9
    assert 0.0 <= blended.score <= 1.0

    fallback = scorer.score(features, card_id="card-unknown")
    assert fallback.mode == "xgb_only"
    assert fallback.gnn_score is None
    assert 0.0 <= fallback.score <= 1.0


def test_scorer_without_gnn_artifacts_serves(scorer):
    result = scorer.score({name: 0.1 for name in scorer.feature_names}, card_id="card-1")
    assert result.mode == "xgb_only"
    assert result.gnn_score is None
