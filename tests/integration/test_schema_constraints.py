"""Database-level guarantees from the Phase 2 migration.

These test the DATABASE, not the API: they prove the schema itself rejects bad
data, even if some future code path forgets to validate. Each test runs inside
a transaction that is rolled back afterwards (see conftest.db_session).
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ProjectMember, ProjectRole, Task, TaskPriority, TaskStatus, User
from tests.factories import add_member, make_project, make_task, make_user

# ---------------------------------------------------------------------------
# Defaults and types
# ---------------------------------------------------------------------------


async def test_id_is_generated_at_flush_not_at_construction(db_session: AsyncSession) -> None:
    user = User(name="Ada", email="ada@example.com", password_hash="x")
    assert user.id is None  # column defaults don't run in __init__

    db_session.add(user)
    await db_session.flush()

    assert user.id is not None  # set during the INSERT, still before any commit


async def test_defaults_are_applied(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)
    task = await make_task(db_session, project, owner)

    assert owner.is_active is True
    assert task.status is TaskStatus.TODO
    assert task.priority is TaskPriority.MEDIUM
    assert task.completed_at is None
    # timestamptz columns come back timezone-aware
    assert task.created_at.tzinfo is not None


async def test_enums_are_stored_as_lowercase_values(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)
    task = await make_task(db_session, project, owner, status=TaskStatus.IN_PROGRESS)

    stored = await db_session.scalar(
        text("SELECT status FROM tasks WHERE id = :id"), {"id": task.id}
    )

    assert stored == "in_progress"  # the value, not the name "IN_PROGRESS"


async def test_invalid_enum_value_rejected_by_database(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)

    # Raw SQL bypasses Python's enum validation, so this reaches the CHECK constraint.
    with pytest.raises(IntegrityError, match="ck_tasks_task_status"):
        await db_session.execute(
            text(
                "INSERT INTO tasks (project_id, title, status, created_by) "
                "VALUES (:project_id, 'Valid title', 'blocked', :user_id)"
            ),
            {"project_id": project.id, "user_id": owner.id},
        )


async def test_updated_at_is_readable_after_update(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)
    task = await make_task(db_session, project, owner)

    task.title = "Renamed task"
    await db_session.flush()

    # eager_defaults fetched the new value via RETURNING. Without it, this
    # attribute access would need a hidden query and raise in async code.
    assert task.updated_at is not None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


async def test_email_is_unique_ignoring_case(db_session: AsyncSession) -> None:
    await make_user(db_session, email="john@example.com")

    with pytest.raises(IntegrityError, match="uq_users_email_lower"):
        await make_user(db_session, email="John@Example.COM")


# ---------------------------------------------------------------------------
# Project membership
# ---------------------------------------------------------------------------


async def test_duplicate_membership_rejected(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    member = await make_user(db_session)
    project = await make_project(db_session, owner)
    await add_member(db_session, project, member)

    with pytest.raises(IntegrityError, match="uq_project_members_project_id_user_id"):
        await add_member(db_session, project, member, role=ProjectRole.ADMIN)


async def test_second_owner_rejected(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    other = await make_user(db_session)
    project = await make_project(db_session, owner)
    await add_member(db_session, project, owner, role=ProjectRole.OWNER)

    with pytest.raises(IntegrityError, match="uq_project_members_one_owner_per_project"):
        await add_member(db_session, project, other, role=ProjectRole.OWNER)


async def test_many_admins_and_owners_of_different_projects_allowed(
    db_session: AsyncSession,
) -> None:
    owner = await make_user(db_session)
    admin_a = await make_user(db_session)
    admin_b = await make_user(db_session)
    project_1 = await make_project(db_session, owner)
    project_2 = await make_project(db_session, owner)

    # The partial index only covers role = 'owner' rows, per project.
    await add_member(db_session, project_1, owner, role=ProjectRole.OWNER)
    await add_member(db_session, project_2, owner, role=ProjectRole.OWNER)
    await add_member(db_session, project_1, admin_a, role=ProjectRole.ADMIN)
    await add_member(db_session, project_1, admin_b, role=ProjectRole.ADMIN)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


async def test_task_title_shorter_than_3_rejected(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)

    with pytest.raises(IntegrityError, match="ck_tasks_title_min_length"):
        await make_task(db_session, project, owner, title="ab")


@pytest.mark.parametrize(
    ("status", "completed_at"),
    [
        (TaskStatus.DONE, None),  # done but no completion time
        (TaskStatus.TODO, datetime(2026, 1, 1, tzinfo=UTC)),  # not done but "completed"
    ],
)
async def test_completed_at_must_match_status(
    db_session: AsyncSession, status: TaskStatus, completed_at: datetime | None
) -> None:
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)

    with pytest.raises(IntegrityError, match="ck_tasks_completed_at_matches_status"):
        await make_task(db_session, project, owner, status=status, completed_at=completed_at)


async def test_done_task_with_completed_at_accepted(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)

    task = await make_task(
        db_session, project, owner, status=TaskStatus.DONE, completed_at=datetime.now(UTC)
    )

    assert task.status is TaskStatus.DONE


# ---------------------------------------------------------------------------
# Delete behavior
# ---------------------------------------------------------------------------


async def test_deleting_project_deletes_its_members_and_tasks(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)
    await add_member(db_session, project, owner, role=ProjectRole.OWNER)
    await make_task(db_session, project, owner)
    await make_task(db_session, project, owner)

    await db_session.delete(project)
    await db_session.flush()

    members = await db_session.scalar(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == project.id)
    )
    tasks = await db_session.scalar(
        select(func.count()).select_from(Task).where(Task.project_id == project.id)
    )
    assert (members, tasks) == (0, 0)


async def test_deleting_assignee_unassigns_task(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    assignee = await make_user(db_session)
    project = await make_project(db_session, owner)
    task = await make_task(db_session, project, owner, assignee_id=assignee.id)

    await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": assignee.id})
    await db_session.refresh(task)

    assert task.assignee_id is None  # ON DELETE SET NULL


async def test_user_who_created_tasks_cannot_be_deleted(db_session: AsyncSession) -> None:
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)
    await make_task(db_session, project, owner)

    with pytest.raises(IntegrityError, match="fk_"):  # ON DELETE RESTRICT
        await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": owner.id})


# ---------------------------------------------------------------------------
# Relationships in async code
# ---------------------------------------------------------------------------


async def test_unloaded_relationship_raises_instead_of_querying(
    db_session: AsyncSession,
) -> None:
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)
    await make_task(db_session, project, owner)
    db_session.expunge_all()  # forget cached objects, like a fresh request

    task = await db_session.scalar(select(Task))
    assert task is not None
    with pytest.raises(InvalidRequestError, match="lazy='raise'"):
        _ = task.project  # lazy="raise": no hidden query

    # The right way: say up front which relationships to load.
    loaded = await db_session.scalar(
        select(Task).where(Task.id == task.id).options(selectinload(Task.project))
    )
    assert loaded is not None
    assert loaded.project.name == "Test Project"
