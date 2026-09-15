from pathlib import Path
import sys

SERVER_DIR = Path(__file__).resolve().parents[1]

if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app import app
from database.db import db
from database.models import Workspace, WorkspaceMember


def migrate_workspace_ownership():
    changed = 0
    repaired_missing_creator = 0
    normalized_other_owners = 0

    with app.app_context():
        workspaces = (
            Workspace.query
            .order_by(Workspace.id.asc())
            .all()
        )

        for workspace in workspaces:
            memberships = (
                WorkspaceMember.query
                .filter_by(workspace_id=workspace.id)
                .order_by(WorkspaceMember.id.asc())
                .all()
            )

            creator_membership = next(
                (
                    membership
                    for membership in memberships
                    if membership.user_id == workspace.created_by
                ),
                None,
            )

            if creator_membership is None:
                creator_membership = WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=workspace.created_by,
                    role="owner",
                )
                db.session.add(creator_membership)
                repaired_missing_creator += 1

            elif creator_membership.role != "owner":
                creator_membership.role = "owner"
                changed += 1

            for membership in memberships:
                if (
                    membership.user_id != workspace.created_by
                    and membership.role == "owner"
                ):
                    membership.role = "admin"
                    normalized_other_owners += 1

        db.session.commit()

    print("Workspace ownership migration completed.")
    print(f"Creator memberships changed to owner: {changed}")
    print(
        f"Missing creator memberships repaired: "
        f"{repaired_missing_creator}"
    )
    print(
        f"Non-creator owners normalized to admin: "
        f"{normalized_other_owners}"
    )


if __name__ == "__main__":
    migrate_workspace_ownership()
