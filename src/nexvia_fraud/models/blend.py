"""Logistic blending of XGBoost and GNN probabilities in log-odds space."""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

EPSILON = 1e-6


def _logit(probability: float) -> float:
    probability = float(np.clip(probability, EPSILON, 1.0 - EPSILON))
    return float(np.log(probability / (1.0 - probability)))


def fit_blender(xgb_prob: np.ndarray, gnn_prob: np.ndarray, y: np.ndarray) -> dict:
    xgb_prob = np.asarray(xgb_prob, dtype=float)
    gnn_prob = np.asarray(gnn_prob, dtype=float)
    y = np.asarray(y, dtype=int)

    if len(y) == 0 or len(np.unique(y)) < 2:
        return {
            "coef": [1.0, 0.0],
            "intercept": 0.0,
            "n": int(len(y)),
        }

    features = np.column_stack(
        [
            [_logit(value) for value in xgb_prob],
            [_logit(value) for value in gnn_prob],
        ]
    )
    model = LogisticRegression().fit(features, y)
    return {
        "coef": [float(value) for value in model.coef_[0]],
        "intercept": float(model.intercept_[0]),
        "n": int(len(y)),
    }


def apply_blender(blend: dict, xgb_prob: float, gnn_prob: float) -> float:
    z = (
        float(blend["coef"][0]) * _logit(xgb_prob)
        + float(blend["coef"][1]) * _logit(gnn_prob)
        + float(blend["intercept"])
    )
    return float(1.0 / (1.0 + np.exp(-z)))
