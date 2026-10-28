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

    allow_demo_seed: bool = True
    synthetic_dir: str = str(ROOT / "data" / "synthetic")
    storage_backend: str = "local"            # local | s3
    local_storage_dir: str = str(ROOT / ".storage")
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "caresaathi"

    meta_api_base: str = "https://api.meta.ai/v1"
    meta_api_key: str = ""
    meta_spark_model: str = "muse-spark-1.3"
    # Reasoning tokens are billed as output and made one judge call take 37 s, so each job asks for the least that works.
    effort_read: str = "low"        # document transcription and extraction
    effort_judge: str = "minimal"   # second-pass wording judge
    effort_word: str = "minimal"    # explanations, flags, chat
    meta_spark_dev_model: str = "muse-spark-1.3-contributor"
    meta_asr_model: str = "muse-voice-transcribe-1.0"
    allow_contributor_models: bool = False
    # Spend guard (D-50). Prices: USD per million tokens, from dev.meta.ai/docs/pricing-rate-limits.
    spend_limit_usd: float = 3.50          # hard stop for live calls; the hackathon credit is $150, the owner set a $4 working budget
    spend_baseline_usd: float = 0.30       # spent before the ledger existed (owner-reported estimate, rounded up)
    price_contrib_in: float = 0.10
    price_contrib_out: float = 0.20
    price_std_in: float = 1.25
    price_std_out: float = 4.25
    price_voice_per_hour: float = 0.18
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


def production_problems(s: Settings) -> list[str]:
    """When the public address is https the app is treated as deployed: development defaults are not allowed. Returns what to fix."""
    if not s.public_base_url.startswith("https"):
        return []
    out = []
    for name in ("jwt_secret", "token_pepper"):
        v = getattr(s, name)
        if v.startswith("dev-only") or len(v) < 24:
            out.append(f"{name.upper()} must be a random value of at least 24 characters")
    for name in ("database_url_app", "database_url_auth", "database_url_worker"):
        if "change-me" in getattr(s, name):
            out.append(f"{name.upper()} still uses the default change-me password; set the role password first (docs/19-deployment.md)")
    if s.allow_demo_seed and s.model_mode == "live" and "ALLOW_DEMO_SEED" not in __import__("os").environ:
        out.append("set ALLOW_DEMO_SEED explicitly (true keeps the demo family button, false removes it)")
    return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
