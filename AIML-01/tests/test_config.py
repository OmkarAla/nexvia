from nexvia_fraud.config import Settings, get_settings


def test_defaults():
    s = Settings()
    assert s.raw_topic == "transactions.raw"
    assert s.alert_threshold == 0.5


def test_env_override(monkeypatch):
    monkeypatch.setenv("ALERT_THRESHOLD", "0.7")
    get_settings.cache_clear()
    assert get_settings().alert_threshold == 0.7
