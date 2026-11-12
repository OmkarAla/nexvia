"""Environment-backed settings for the fraud service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/dev.db"
    kafka_bootstrap: str = "localhost:9092"
    raw_topic: str = "transactions.raw"
    scored_topic: str = "transactions.scored"
    alerts_topic: str = "alerts"
    alert_threshold: float = 0.5
    model_dir: str = "artifacts/demo"
    demo_data_path: str = "data/demo/transactions.csv"
    replay_rate: float = 2.0
    api_url: str = "http://localhost:8000"
    drift_share_threshold: float = 0.3
    drift_min_rows: int = 50
    drift_interval_seconds: int = 60
    drift_reference_path: str = "artifacts/demo/reference_features.parquet"


@lru_cache
def get_settings() -> Settings:
    return Settings()
