from alembic import command

from tests.conftest import alembic_config


def test_models_and_migrations_are_in_sync() -> None:
    """Fails if a model was changed without generating a migration.

    The test database was already built with `alembic upgrade head` (see the
    migrated_test_database fixture). `alembic check` compares it to the models
    and raises if autogenerate would produce any new operation.
    """
    command.check(alembic_config())
