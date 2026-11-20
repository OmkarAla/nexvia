import pandas as pd

from nexvia_fraud.data.load_ieee import load_ieee, summarize_ieee, write_eda_report


def _write_raw(tmp_path):
    transactions = pd.DataFrame(
        {
            "TransactionID": [1, 2, 3],
            "TransactionDT": [0, 3600, 86400],
            "TransactionAmt": [10.0, 20.0, 30.0],
            "card1": [100, 100, 200],
            "P_emaildomain": ["gmail.com", None, "yahoo.com"],
            "R_emaildomain": [None, "outlook.com", None],
            "addr1": [1, 1, 2],
            "isFraud": [0, 1, 0],
        }
    )
    identity = pd.DataFrame(
        {"TransactionID": [1, 3], "DeviceInfo": ["Windows", "iOS"]}
    )
    transactions.to_csv(tmp_path / "train_transaction.csv", index=False)
    identity.to_csv(tmp_path / "train_identity.csv", index=False)


def test_maps_ieee_into_project_schema(tmp_path):
    _write_raw(tmp_path)

    frame = load_ieee(tmp_path)

    assert list(frame.columns) == [
        "transaction_id",
        "card_id",
        "event_time",
        "amount",
        "device_id",
        "email_domain",
        "addr_id",
        "is_fraud",
    ]
    assert frame["event_time"].is_monotonic_increasing
    assert frame["card_id"].tolist() == ["card-100", "card-100", "card-200"]
    assert frame["device_id"].tolist() == ["Windows", "unknown-device", "iOS"]
    assert frame["email_domain"].tolist() == [
        "gmail.com",
        "outlook.com",
        "yahoo.com",
    ]
    assert frame["is_fraud"].tolist() == [0, 1, 0]


def test_limit_samples_deterministically(tmp_path):
    _write_raw(tmp_path)

    first = load_ieee(tmp_path, limit=2, seed=7)
    second = load_ieee(tmp_path, limit=2, seed=7)

    assert len(first) == 2
    assert first.equals(second)


def test_summary_and_report(tmp_path):
    _write_raw(tmp_path)
    frame = load_ieee(tmp_path)

    summary = summarize_ieee(tmp_path, frame)
    assert summary["rows_raw"] == 3
    assert 0.0 <= summary["fraud_rate_raw"] <= 1.0
    assert summary["cards"] == 2

    report = tmp_path / "eda.md"
    write_eda_report(summary, report)
    assert "Class imbalance" in report.read_text()
