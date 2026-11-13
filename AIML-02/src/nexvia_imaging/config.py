"""Environment-backed settings for the imaging service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/dev.db"
    orthanc_url: str = "http://localhost:8042"
    orthanc_user: str = "orthanc"
    orthanc_password: str = "orthanc"
    demo_data_dir: str = "data/demo"
    model_dir: str = "artifacts/demo"
    poll_interval_seconds: int = 5
    decision_threshold: float = 0.5


@lru_cache
def get_settings() -> Settings:
    return Settings()
