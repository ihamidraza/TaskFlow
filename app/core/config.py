"""Typed application settings, loaded from environment variables and `.env`.

NestJS comparison: this replaces `ConfigModule` + a Joi validation schema.
Each attribute is an env var (case-insensitive): `database_url` <- DATABASE_URL.
Pydantic validates and converts types, so a bad value fails at startup,
not halfway through a request.
"""

from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends, Request
from pydantic import Field, PostgresDsn, SecretStr, model_validator
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
    # min_length=32: HS256 keys shorter than 32 bytes are brute-forceable.
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    # `iss` and `aud` claims: who issued the token, and who it's meant for.
    # Tokens minted for another service (even with the same secret) are rejected.
    jwt_issuer: str = "taskflow-api"
    jwt_audience: str = "taskflow-api"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=24 * 60)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @model_validator(mode="after")
    def _no_debug_in_production(self) -> "Settings":
        # Runs after all fields are validated: cross-field rules go here.
        if self.app_env == "production" and self.debug:
            raise ValueError("DEBUG must be false when APP_ENV=production")
        return self

    @model_validator(mode="after")
    def _no_placeholder_secret(self) -> "Settings":
        if self.jwt_secret.get_secret_value() == PLACEHOLDER_JWT_SECRET:
            raise ValueError("JWT_SECRET is still the .env.example placeholder; generate one")
        return self


# The value shipped in .env.example. Refusing it means nobody runs with a
# publicly known secret by forgetting to change it.
PLACEHOLDER_JWT_SECRET = "replace-with-secure-random-secret"


def get_app_settings(request: Request) -> Settings:
    """FastAPI dependency: the Settings the running app was built with.

    Reading them from app.state (instead of calling get_settings()) means a
    test app built with create_app(test_settings) uses its test settings
    everywhere, including inside dependencies.
    """
    settings: Settings = request.app.state.settings
    return settings


@lru_cache
def get_settings() -> Settings:
    """Build Settings once and reuse it (lru_cache makes this a cheap singleton).

    Using a function instead of a module-level `settings = Settings()` means
    importing this module never reads the environment by itself, and tests can
    clear the cache (`get_settings.cache_clear()`) to load different values.
    """
    return Settings()  # values come from the environment


# Use as a parameter type: `settings: SettingsDep`.
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
