"""Who may ATTEMPT each project action, as pure functions of roles.

No database, no FastAPI: just `role in, bool out`. That makes the spec's
authorization matrix (section 4.2) directly unit-testable, cell by cell.

These answer "is this role allowed to try?" (403 if not). Structural rules
that apply to everyone, like "the owner can't be removed", are separate
checks in the service (400).
"""

from app.modules.projects.model import ProjectRole

OWNER = ProjectRole.OWNER
ADMIN = ProjectRole.ADMIN
MEMBER = ProjectRole.MEMBER


def can_view_project(actor: ProjectRole) -> bool:
    return True  # being a member at all is the requirement


def can_update_project(actor: ProjectRole) -> bool:
    return actor in (OWNER, ADMIN)


def can_delete_project(actor: ProjectRole) -> bool:
    return actor is OWNER


def can_manage_tasks(actor: ProjectRole) -> bool:
    return True  # spec: all members can create/update/assign/delete tasks (Phase 5)


def can_add_member(actor: ProjectRole, new_role: ProjectRole) -> bool:
    """Owners may add admins or members; admins may add regular members only."""
    if actor is OWNER:
        return True
    if actor is ADMIN:
        return new_role is MEMBER
    return False


def can_change_member_role(actor: ProjectRole) -> bool:
    """Only the owner changes roles (admins can't promote anyone to admin)."""
    return actor is OWNER


def can_remove_member(actor: ProjectRole, target: ProjectRole) -> bool:
    """Owners may remove admins and members; admins may remove regular members only."""
    if actor is OWNER:
        return True
    if actor is ADMIN:
        return target is MEMBER
    return False


def can_transfer_ownership(actor: ProjectRole) -> bool:
    return actor is OWNER
