from nexvia_imaging.config import Settings, get_settings


def test_defaults():
    settings = Settings()
    assert settings.orthanc_url == "http://localhost:8042"
    assert settings.poll_interval_seconds == 5


def test_env_override(monkeypatch):
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "11")
    get_settings.cache_clear()
    assert get_settings().poll_interval_seconds == 11
