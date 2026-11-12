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
