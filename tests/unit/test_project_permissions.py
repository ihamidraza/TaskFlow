"""The spec's authorization matrix (PROJECT_CONTEXT.md, section 4.2), cell by cell."""

from collections.abc import Callable

import pytest

from app.modules.projects import permissions as p
from app.modules.projects.model import ProjectRole

OWNER, ADMIN, MEMBER = ProjectRole.OWNER, ProjectRole.ADMIN, ProjectRole.MEMBER

# operation -> (check, expected result for (owner, admin, member))
MATRIX: dict[str, tuple[Callable[[ProjectRole], bool], tuple[bool, bool, bool]]] = {
    "view project": (p.can_view_project, (True, True, True)),
    "update project": (p.can_update_project, (True, True, False)),
    "delete project": (p.can_delete_project, (True, False, False)),
    "list/create/update/delete tasks": (p.can_manage_tasks, (True, True, True)),
    "add regular members": (lambda r: p.can_add_member(r, MEMBER), (True, True, False)),
    "remove regular members": (lambda r: p.can_remove_member(r, MEMBER), (True, True, False)),
    "add as admin": (lambda r: p.can_add_member(r, ADMIN), (True, False, False)),
    "promote to admin": (p.can_change_member_role, (True, False, False)),
    "transfer ownership": (p.can_transfer_ownership, (True, False, False)),
}

CASES = [
    pytest.param(check, role, expected, id=f"{operation}-{role.value}")
    for operation, (check, row) in MATRIX.items()
    for role, expected in zip((OWNER, ADMIN, MEMBER), row, strict=True)
]


@pytest.mark.parametrize(("check", "role", "expected"), CASES)
def test_authorization_matrix(
    check: Callable[[ProjectRole], bool], role: ProjectRole, expected: bool
) -> None:
    assert check(role) is expected


def test_admin_cannot_remove_another_admin() -> None:
    assert p.can_remove_member(ADMIN, ADMIN) is False
    assert p.can_remove_member(OWNER, ADMIN) is True
