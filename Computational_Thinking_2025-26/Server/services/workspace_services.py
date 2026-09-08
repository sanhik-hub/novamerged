from database.db import db
from database.models import (
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceSettings,
)
import secrets
import string


def _generate_join_code(length=8):
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(length))

        existing = Workspace.query.filter_by(join_code=code).first()

        if not existing:
            return code


def create_workspace(username: str, name: str):
    user = User.query.filter_by(username=username).first()

    if not user:
        return None, "User not found"

    name = name.strip()

    if not name:
        return None, "Workspace name cannot be empty"

    if len(name) > 120:
        return None, "Workspace name is too long"

    try:
        join_code = _generate_join_code()

        workspace = Workspace(
            name=name,
            join_code=join_code,
            created_by=user.id,
            status="active",
        )

        db.session.add(workspace)
        db.session.flush()

        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role="admin",
        )

        settings = WorkspaceSettings(
            workspace_id=workspace.id,
            computation_mode="offline",
            allow_member_posting=False,
            allow_member_solving=True,
        )

        db.session.add(member)
        db.session.add(settings)

        db.session.commit()

        return {
            "id": workspace.id,
            "name": workspace.name,
            "join_code": workspace.join_code,
            "role": "admin",
            "computation_mode": settings.computation_mode,
            "allow_member_posting": settings.allow_member_posting,
            "allow_member_solving": settings.allow_member_solving,
        }, None

    except Exception:
        db.session.rollback()
        return None, "Failed to create workspace"


def join_workspace(username: str, join_code: str):
    user = User.query.filter_by(username=username).first()

    if not user:
        return None, "User not found"

    join_code = join_code.strip().upper()

    workspace = Workspace.query.filter_by(
        join_code=join_code,
        status="active",
    ).first()

    if not workspace:
        return None, "Invalid workspace join code"

    existing_member = WorkspaceMember.query.filter_by(
        workspace_id=workspace.id,
        user_id=user.id,
    ).first()

    if existing_member:
        return None, "User is already a member of this workspace"

    try:
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role="member",
        )

        db.session.add(member)
        db.session.commit()

        return {
            "id": workspace.id,
            "name": workspace.name,
            "join_code": workspace.join_code,
            "role": "member",
        }, None

    except Exception:
        db.session.rollback()
        return None, "Failed to join workspace"


def get_user_workspaces(username: str):
    user = User.query.filter_by(username=username).first()

    if not user:
        return None, "User not found"

    try:
        memberships = (
            WorkspaceMember.query
            .join(
                Workspace,
                Workspace.id == WorkspaceMember.workspace_id,
            )
            .filter(
                WorkspaceMember.user_id == user.id,
                Workspace.status == "active",
            )
            .order_by(Workspace.id.desc())
            .all()
        )

        result = []

        for membership in memberships:
            workspace = Workspace.query.get(membership.workspace_id)

            if not workspace:
                continue

            result.append({
                "id": workspace.id,
                "name": workspace.name,
                "join_code": workspace.join_code,
                "role": membership.role,
                "created_by": workspace.created_by,
                "created_at": (
                    workspace.created_at.isoformat()
                    if workspace.created_at
                    else None
                ),
            })

        return result, None

    except Exception:
        return None, "Failed to retrieve workspaces"


def get_workspace_details(username: str, workspace_id: int):
    user = User.query.filter_by(username=username).first()

    if not user:
        return None, "User not found"

    membership = WorkspaceMember.query.filter_by(
        workspace_id=workspace_id,
        user_id=user.id,
    ).first()

    if not membership:
        return None, "You are not a member of this workspace"

    workspace = Workspace.query.filter_by(
        id=workspace_id,
        status="active",
    ).first()

    if not workspace:
        return None, "Workspace not found"

    settings = WorkspaceSettings.query.filter_by(
        workspace_id=workspace.id
    ).first()

    member_count = WorkspaceMember.query.filter_by(
        workspace_id=workspace.id
    ).count()

    return {
        "id": workspace.id,
        "name": workspace.name,
        "join_code": workspace.join_code,
        "role": membership.role,
        "created_by": workspace.created_by,
        "created_at": (
            workspace.created_at.isoformat()
            if workspace.created_at
            else None
        ),
        "member_count": member_count,
        "settings": {
            "computation_mode": (
                settings.computation_mode
                if settings
                else "offline"
            ),
            "allow_member_posting": (
                settings.allow_member_posting
                if settings
                else False
            ),
            "allow_member_solving": (
                settings.allow_member_solving
                if settings
                else True
            ),
        },
    }, None


def leave_workspace(username: str, workspace_id: int):
    user = User.query.filter_by(username=username).first()

    if not user:
        return None, "User not found"

    membership = WorkspaceMember.query.filter_by(
        workspace_id=workspace_id,
        user_id=user.id,
    ).first()

    if not membership:
        return None, "You are not a member of this workspace"

    if membership.role == "admin":
        return None, (
            "Workspace admins cannot leave the workspace. "
            "Transfer administration first."
        )

    try:
        db.session.delete(membership)
        db.session.commit()

        return {
            "workspace_id": workspace_id,
            "message": "You have left the workspace",
        }, None

    except Exception:
        db.session.rollback()
        return None, "Failed to leave workspace"