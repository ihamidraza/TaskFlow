"""Typed application settings, loaded from environment variables and `.env`.

NestJS comparison: this replaces `ConfigModule` + a Joi validation schema.
Each attribute is an env var (case-insensitive): `database_url` <- DATABASE_URL.
Pydantic validates and converts types, so a bad value fails at startup,
not halfway through a request.
"""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unrelated variables in .env
    )

    app_name: str = "TaskFlow API"
    app_env: Literal["development", "testing", "production"] = "development"
    debug: bool = False

    # No default -> REQUIRED. Missing value = app refuses to start (fail fast).
    database_url: PostgresDsn

    # SecretStr hides the value in repr()/logs: prints as '**********'.
    # Read the real value explicitly with .get_secret_value().
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = 30

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @model_validator(mode="after")
    def _no_debug_in_production(self) -> "Settings":
        # Runs after all fields are validated: cross-field rules go here.
        if self.app_env == "production" and self.debug:
            raise ValueError("DEBUG must be false when APP_ENV=production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Build Settings once and reuse it (lru_cache makes this a cheap singleton).

    Using a function instead of a module-level `settings = Settings()` means
    importing this module never reads the environment by itself, and tests can
    clear the cache (`get_settings.cache_clear()`) to load different values.
    """
    return Settings()  # values come from the environment
