from nexvia_fraud.data.generate_demo import generate_demo_transactions


def test_schema_and_determinism():
    a = generate_demo_transactions(500, seed=3)
    b = generate_demo_transactions(500, seed=3)
    assert list(a.columns) == [
        "transaction_id",
        "card_id",
        "event_time",
        "amount",
        "device_id",
        "email_domain",
        "addr_id",
        "is_fraud",
    ]
    assert a.equals(b)
    assert len(a) == 500


def test_prevalence_and_rings():
    df = generate_demo_transactions(5000, seed=7)
    rate = df.is_fraud.mean()
    assert 0.02 <= rate <= 0.08
    ring_devices = df.loc[df.is_fraud == 1, "device_id"]
    assert ring_devices.duplicated().any()
    assert df.loc[df.is_fraud == 1, "card_id"].nunique() < df.loc[df.is_fraud == 1].shape[0]


def test_event_times_increasing_per_card():
    df = generate_demo_transactions(2000, seed=11)
    for _, group in df.groupby("card_id"):
        assert group.event_time.is_monotonic_increasing
