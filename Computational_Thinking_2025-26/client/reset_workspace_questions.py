from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from Server.app import app
from Server.database.db import db


def find_workspace_question_table():
    candidates = []

    for name, table in db.metadata.tables.items():
        lower = name.lower()
        if "workspace_question" in lower:
            candidates.append(table)

    if not candidates:
        raise RuntimeError(
            "Could not find a WorkspaceQuestion table in the loaded database metadata."
        )

    # Prefer the actual question table, not solution/attempt/follow-up tables.
    for table in candidates:
        if table.name.lower() == "workspace_question":
            return table

    candidates.sort(key=lambda t: len(t.name))
    return candidates[0]


def get_dependent_tables(target):
    result = []

    for table in db.metadata.tables.values():
        if table is target:
            continue

        for foreign_key in table.foreign_keys:
            if foreign_key.column.table is target:
                result.append((table, foreign_key.parent, foreign_key.column))

    return result


with app.app_context():
    target = find_workspace_question_table()

    print("")
    print("========================================")
    print(" NOVA WORKSPACE QUESTION RESET")
    print("========================================")
    print(f"Question table: {target.name}")

    question_count = db.session.execute(
        db.select(db.func.count()).select_from(target)
    ).scalar_one()

    print(f"Existing Workspace questions: {question_count}")

    if question_count == 0:
        print("Nothing to delete.")
        raise SystemExit(0)

    dependents = get_dependent_tables(target)

    print("")
    print("Linked dependent tables:")
    if dependents:
        for table, child_column, parent_column in dependents:
            print(
                f"  {table.name}: "
                f"{child_column.name} -> {parent_column.name}"
            )
    else:
        print("  None detected by SQLAlchemy metadata.")

    print("")
    print("This will delete Workspace question data only.")
    print("Users, workspaces, memberships and settings will NOT be deleted.")

    answer = input("Type DELETE WORKSPACE QUESTIONS to continue: ").strip()

    if answer != "DELETE WORKSPACE QUESTIONS":
        print("Cancelled. No database changes were made.")
        raise SystemExit(0)

    deleted_dependents = 0

    # Delete directly-linked child records first.
    for table, child_column, parent_column in dependents:
        statement = db.delete(table).where(
            child_column.in_(
                db.select(parent_column)
            )
        )

        result = db.session.execute(statement)
        count = result.rowcount or 0

        if count:
            print(f"Deleted {count} rows from {table.name}")
            deleted_dependents += count

    result = db.session.execute(db.delete(target))
    deleted_questions = result.rowcount or 0

    db.session.commit()

    remaining = db.session.execute(
        db.select(db.func.count()).select_from(target)
    ).scalar_one()

    print("")
    print("========================================")
    print(" RESET COMPLETE")
    print("========================================")
    print(f"Workspace questions deleted: {deleted_questions}")
    print(f"Linked rows deleted: {deleted_dependents}")
    print(f"Workspace questions remaining: {remaining}")

    if remaining != 0:
        raise RuntimeError(
            f"Reset verification failed: {remaining} questions remain."
        )
