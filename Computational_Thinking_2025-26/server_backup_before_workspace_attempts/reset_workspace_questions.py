from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app import app
from database.db import db
from database.models import (
    WorkspaceQuestion,
    WorkspaceQuestionSolution,
    WorkspaceQuestionAttempt,
    WorkspaceQuestionFollowUp,
)

with app.app_context():
    questions = WorkspaceQuestion.query.all()

    print("")
    print("========================================")
    print(" NOVA WORKSPACE QUESTION RESET")
    print("========================================")
    print(f"Workspace questions found: {len(questions)}")

    if not questions:
        print("Nothing to delete.")
        raise SystemExit(0)

    print("")
    print("This will delete:")
    print("  - Workspace questions")
    print("  - Stored solutions")
    print("  - Attempts")
    print("  - Follow-ups")
    print("")
    print("This will NOT delete:")
    print("  - Users")
    print("  - Workspaces")
    print("  - Workspace memberships")
    print("  - Workspace settings")
    print("  - Invitations")
    print("")

    answer = input(
        "Type DELETE WORKSPACE QUESTIONS to continue: "
    ).strip()

    if answer != "DELETE WORKSPACE QUESTIONS":
        print("Cancelled. No database changes were made.")
        raise SystemExit(0)

    question_ids = [q.id for q in questions]

    deleted_followups = (
        WorkspaceQuestionFollowUp.query
        .filter(
            WorkspaceQuestionFollowUp.workspace_question_id.in_(question_ids)
        )
        .delete(synchronize_session=False)
    )

    deleted_attempts = (
        WorkspaceQuestionAttempt.query
        .filter(
            WorkspaceQuestionAttempt.workspace_question_id.in_(question_ids)
        )
        .delete(synchronize_session=False)
    )

    deleted_solutions = (
        WorkspaceQuestionSolution.query
        .filter(
            WorkspaceQuestionSolution.workspace_question_id.in_(question_ids)
        )
        .delete(synchronize_session=False)
    )

    deleted_questions = (
        WorkspaceQuestion.query
        .filter(
            WorkspaceQuestion.id.in_(question_ids)
        )
        .delete(synchronize_session=False)
    )

    db.session.commit()

    remaining_questions = WorkspaceQuestion.query.count()
    remaining_solutions = WorkspaceQuestionSolution.query.count()
    remaining_attempts = WorkspaceQuestionAttempt.query.count()
    remaining_followups = WorkspaceQuestionFollowUp.query.count()

    print("")
    print("========================================")
    print(" RESET COMPLETE")
    print("========================================")
    print(f"Questions deleted:   {deleted_questions}")
    print(f"Solutions deleted:  {deleted_solutions}")
    print(f"Attempts deleted:   {deleted_attempts}")
    print(f"Follow-ups deleted: {deleted_followups}")
    print("")
    print(f"Questions remaining:   {remaining_questions}")
    print(f"Solutions remaining:  {remaining_solutions}")
    print(f"Attempts remaining:    {remaining_attempts}")
    print(f"Follow-ups remaining:  {remaining_followups}")

    if any(
        value != 0
        for value in (
            remaining_questions,
            remaining_solutions,
            remaining_attempts,
            remaining_followups,
        )
    ):
        raise RuntimeError(
            "Reset verification failed: Workspace question data remains."
        )
