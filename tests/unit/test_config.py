import pytest
from pydantic import ValidationError

from app.core.config import PLACEHOLDER_JWT_SECRET, Settings
from tests.conftest import make_test_settings


def test_missing_database_url_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("JWT_SECRET", "x")

    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_values_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/x")
    monkeypatch.setenv("JWT_SECRET", "s" * 32)
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")

    settings = Settings(_env_file=None)

    assert settings.database_url.hosts()[0]["host"] == "db"
    assert settings.access_token_expire_minutes == 15  # "15" string -> int


def test_jwt_secret_is_masked() -> None:
    settings = make_test_settings(jwt_secret="super-secret-value-that-is-32-chars")

    assert "super-secret" not in repr(settings)
    assert settings.jwt_secret.get_secret_value() == "super-secret-value-that-is-32-chars"


def test_debug_forbidden_in_production() -> None:
    with pytest.raises(ValidationError, match="DEBUG must be false"):
        make_test_settings(app_env="production", debug=True)


def test_invalid_log_level_rejected() -> None:
    with pytest.raises(ValidationError):
        make_test_settings(log_level="LOUD")


def test_short_jwt_secret_rejected() -> None:
    with pytest.raises(ValidationError, match="jwt_secret"):
        make_test_settings(jwt_secret="too-short")


def test_placeholder_jwt_secret_rejected() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        make_test_settings(jwt_secret=PLACEHOLDER_JWT_SECRET)
