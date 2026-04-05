import json
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "Corvin"
    environment: str = "development"
    log_level: str = "INFO"
    allowed_origins: List[str] = ["http://localhost:3000"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # Database
    database_url: str = "postgresql+asyncpg://corvin:changeme@localhost:5432/corvin"

    @field_validator("database_url", mode="before")
    @classmethod
    def ensure_async_driver(cls, v: object) -> object:
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # MFA
    mfa_issuer: str = "Corvin"

    # API Keys
    hibp_api_key: str = ""
    virustotal_api_key: str = ""
    google_safe_browsing_api_key: str = ""
    sendgrid_api_key: str = ""

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # File upload
    max_upload_size_mb: int = 10
    upload_dir: str = "/uploads"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
