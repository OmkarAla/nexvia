import pandas as pd
import pytest

from nexvia_fraud.features.service import FeatureService

EXPECTED_NAMES = [
    "velocity_1h",
    "velocity_24h",
    "unique_devices_24h",
    "amount_mean",
    "amount_std",
    "amount_zscore",
    "device_change",
    "email_change",
    "addr_change",
    "seconds_since_last_txn",
    "device_share_count",
    "email_share_count",
    "addr_share_count",
]


def _fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(
                transaction_id="t1",
                card_id="c1",
                event_time=pd.Timestamp("2026-01-01T00:00:00Z"),
                amount=10.0,
                device_id="d1",
                email_domain="a.com",
                addr_id="x",
                is_fraud=0,
            ),
            dict(
                transaction_id="t2",
                card_id="c1",
                event_time=pd.Timestamp("2026-01-01T00:30:00Z"),
                amount=30.0,
                device_id="d2",
                email_domain="a.com",
                addr_id="x",
                is_fraud=0,
            ),
            dict(
                transaction_id="t3",
                card_id="c2",
                event_time=pd.Timestamp("2026-01-01T00:40:00Z"),
                amount=12.0,
                device_id="d2",
                email_domain="a.com",
                addr_id="y",
                is_fraud=1,
            ),
        ]
    )


def test_feature_names_order():
    service = FeatureService.from_dataframe(_fixture())
    assert service.feature_names() == EXPECTED_NAMES


def test_counts_exclude_current_event():
    service = FeatureService.from_dataframe(_fixture())
    f = service.get_features("c1", pd.Timestamp("2026-01-01T00:30:00Z"), 30.0, "d2", "a.com", "x")
    assert f["velocity_1h"] == 1.0
    assert f["velocity_24h"] == 1.0
    assert f["unique_devices_24h"] == 1.0
    assert f["amount_mean"] == 10.0
    assert f["amount_std"] == 0.0
    assert f["amount_zscore"] == 0.0
    assert f["device_change"] == 1.0
    assert f["email_change"] == 0.0
    assert f["addr_change"] == 0.0
    assert f["seconds_since_last_txn"] == 1800.0
    # at 00:30 the d2 device has not been seen yet and a.com only by c1
    assert f["device_share_count"] == 0.0
    assert f["email_share_count"] == 1.0
    assert f["addr_share_count"] == 1.0


def test_share_counts_capture_rings():
    service = FeatureService.from_dataframe(_fixture())
    f = service.get_features("c2", pd.Timestamp("2026-01-01T00:40:00Z"), 12.0, "d2", "a.com", "y")
    assert f["device_share_count"] == 1.0  # c1 used d2
    assert f["email_share_count"] == 1.0
    assert f["addr_share_count"] == 0.0


def test_unknown_card_defaults():
    service = FeatureService.from_dataframe(_fixture())
    f = service.get_features("nope", pd.Timestamp("2026-01-01T00:30:00Z"), 5.0, "d9", "b.com", "y")
    expected = {name: 0.0 for name in EXPECTED_NAMES}
    expected["seconds_since_last_txn"] = -1.0
    assert f == expected


def test_naive_event_time_rejected():
    service = FeatureService.from_dataframe(_fixture())
    with pytest.raises(ValueError):
        service.get_features("c1", pd.Timestamp("2026-01-01T00:30:00"), 1.0, "d1", "a.com", "x")
