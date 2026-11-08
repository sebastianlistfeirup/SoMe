from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SoMe-maskinen"
    app_env: str = "development"
    app_timezone: str = "Europe/Copenhagen"
    app_secret_key: str = ""
    database_url: str = "sqlite:///./data/some.db"
    data_dir: Path = Path("./data")
    model_cache_dir: Path = Path("./models")
    dry_run: bool = True
    publish_enabled: bool = False
    paid_jobs_enabled: bool = False
    monthly_ai_budget_dkk: float = Field(default=150, gt=0)
    max_job_ai_cost_dkk: float = Field(default=5, gt=0)
    worker_concurrency: int = Field(default=1, ge=1, le=1)
    worker_poll_seconds: float = 2.0
    render_max_seconds: int = 600
    download_max_bytes: int = 200_000_000
    download_timeout_seconds: int = 20
    anthropic_api_key: str = ""
    claude_model_text: str = ""
    claude_model_vision: str = ""
    claude_input_dkk_per_million: float = Field(default=0, ge=0)
    claude_output_dkk_per_million: float = Field(default=0, ge=0)
    youtube_api_key: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_refresh_token: str = ""
    meta_access_token: str = ""
    meta_instagram_account_id: str = ""
    meta_graph_version: str = ""
    public_base_url: str = ""
    signed_media_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    secure_cookies: bool = False
    session_ttl_minutes: int = 120
    backup_key: str = ""

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
