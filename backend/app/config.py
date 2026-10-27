"""Configuration from environment variables (docs/13-architecture.md section 10). Names only in .env.example."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url_app: str = "postgresql+psycopg://caresaathi_app:change-me-app@127.0.0.1:5432/caresaathi"
    database_url_auth: str = "postgresql+psycopg://caresaathi_auth:change-me-auth@127.0.0.1:5432/caresaathi"
    database_url_worker: str = "postgresql+psycopg://caresaathi_worker:change-me-worker@127.0.0.1:5432/caresaathi"
    database_url_admin: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/caresaathi"

    storage_backend: str = "local"            # local | s3
    local_storage_dir: str = str(ROOT / ".storage")
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "caresaathi"

    meta_api_base: str = "https://api.meta.ai/v1"
    meta_api_key: str = ""
    meta_spark_model: str = "muse-spark-1.3"
    meta_spark_dev_model: str = "muse-spark-1.3-contributor"
    meta_asr_model: str = "muse-voice-transcribe-1.0"
    allow_contributor_models: bool = False
    model_mode: str = "fake"                  # fake | live. Fake runs offline with canned output.

    tts_provider: str = ""
    tts_api_key: str = ""

    jwt_secret: str = "dev-only-change-me"
    token_pepper: str = "dev-only-change-me"
    access_token_minutes: int = 30
    public_base_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    reference_list_require_review: bool = True
    max_upload_bytes: int = 15 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
