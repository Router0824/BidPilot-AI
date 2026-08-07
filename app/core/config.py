from pydantic_settings import BaseSettings
from typing import Optional
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def resolve_path(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


class Settings(BaseSettings):
    APP_NAME: str = "BidPilot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./bidpilot.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "bidpilot-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 200

    # LLM Gateway. Set BIDPILOT_LLM_PROVIDER=deepseek/openai and BIDPILOT_LLM_API_KEY to enable.
    LLM_PROVIDER: str = "mock"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    LLM_FAST_MODEL: Optional[str] = None
    LLM_QUALITY_MODEL: Optional[str] = None
    LLM_MODEL_ROUTING: dict[str, str] = {}
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_COST_LIMIT_PER_PROJECT: float = 0.0
    LLM_ESTIMATED_COST_PER_1K_TOKENS: float = 0.0

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Vector
    EMBEDDING_DIM: int = 768

    # Audit
    AUDIT_RETENTION_DAYS: int = 365

    # Enterprise auth integration placeholders
    LDAP_ENABLED: bool = False
    LDAP_SERVER_URL: Optional[str] = None
    LDAP_BASE_DN: Optional[str] = None
    SSO_ENABLED: bool = False
    SSO_PROVIDER: Optional[str] = None
    SSO_METADATA_URL: Optional[str] = None

    model_config = {"env_prefix": "BIDPILOT_", "env_file": ".env"}


settings = Settings()
settings.UPLOAD_DIR = resolve_path(settings.UPLOAD_DIR)
if settings.DATABASE_URL.startswith("sqlite+aiosqlite:///./"):
    settings.DATABASE_URL = "sqlite+aiosqlite:///" + resolve_path(settings.DATABASE_URL.removeprefix("sqlite+aiosqlite:///"))
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
