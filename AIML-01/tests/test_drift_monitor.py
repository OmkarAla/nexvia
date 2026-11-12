import pandas as pd

from nexvia_fraud.drift.monitor import compute_drift
from nexvia_fraud.features.service import FeatureService


def _features(demo_df, rows: int = 400) -> pd.DataFrame:
    service = FeatureService.from_dataframe(demo_df)
    names = service.feature_names()
    records = []
    for row in demo_df.head(rows).itertuples(index=False):
        values = service.get_features(
            row.card_id,
            row.event_time,
            float(row.amount),
            row.device_id,
            row.email_domain,
            row.addr_id,
        )
        records.append([values[name] for name in names])
    return pd.DataFrame(records, columns=names)


def test_identical_frames_do_not_drift(demo_df):
    reference = _features(demo_df)

    result = compute_drift(reference, reference.copy())

    assert result["drift_share"] == 0.0
    assert result["dataset_drift"] is False
    assert all(not column["drifted"] for column in result["columns"])


def test_shifted_column_is_detected(demo_df):
    reference = _features(demo_df)
    current = reference.copy()
    current["amount_zscore"] = current["amount_zscore"] + 10.0

    result = compute_drift(reference, current)

    drifted = {column["column"] for column in result["columns"] if column["drifted"]}
    assert "amount_zscore" in drifted
    assert result["drift_share"] > 0.0
    assert result["method"] == "evidently:DataDriftPreset"
    assert result["n_reference"] == len(reference)
    assert result["n_current"] == len(current)
    assert all("score" in column and "method" in column for column in result["columns"])
