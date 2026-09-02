from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_version: str = "0.1.0"
    database_url: str = "postgresql+psycopg://fairhire:fairhire_local_only@localhost:5432/fairhire"
    migration_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    oidc_issuer: str = "http://localhost:5556/dex"
    oidc_audience: str = "fairhire-web"
    dev_auth_enabled: bool = True
    allowed_origins: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def prevent_development_auth_in_production(self) -> "Settings":
        if self.app_env == "production" and self.dev_auth_enabled:
            raise ValueError("DEV_AUTH_ENABLED must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
