from app import app
from database.db import db
from database.models import (
    QuestionsNScore,
    WorkspaceQuestion,
    WorkspaceQuestionSolution,
    WorkspaceQuestionAttempt,
    WorkspaceQuestionFollowUp,
)

with app.app_context():
    print("")
    print("================================================")
    print(" SAFE NOVA WORKSPACE QUESTION CLEANUP")
    print("================================================")
    print("")
    print("DATABASE: PostgreSQL")
    print("SCOPE: WORKSPACE QUESTIONS ONLY")
    print("")

    ordinary_before = QuestionsNScore.query.count()
    questions_before = WorkspaceQuestion.query.count()
    solutions_before = WorkspaceQuestionSolution.query.count()
    attempts_before = WorkspaceQuestionAttempt.query.count()
    followups_before = WorkspaceQuestionFollowUp.query.count()

    print("BEFORE")
    print("--------------------------------")
    print(f"Ordinary QuestionsNScore: {ordinary_before}")
    print(f"Workspace questions:      {questions_before}")
    print(f"Workspace solutions:      {solutions_before}")
    print(f"Workspace attempts:       {attempts_before}")
    print(f"Workspace follow-ups:     {followups_before}")
    print("")

    if questions_before == 0:
        print("No workspace questions exist.")
        print("Nothing will be deleted.")
        raise SystemExit(0)

    question_ids = [
        question.id
        for question in WorkspaceQuestion.query.with_entities(
            WorkspaceQuestion.id
        ).all()
    ]

    print(f"Workspace question IDs selected: {len(question_ids)}")
    print("")
    print("ONLY these tables will be modified:")
    print("  workspace_question_followups")
    print("  workspace_question_attempts")
    print("  workspace_question_solutions")
    print("  workspace_questions")
    print("")
    print("QuestionsNScore will NOT be modified.")
    print("Users/workspaces/memberships/settings/invitations will NOT be modified.")
    print("")

    try:
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

        # IMPORTANT:
        # Verify BEFORE committing.
        ordinary_after = QuestionsNScore.query.count()
        questions_after = WorkspaceQuestion.query.count()
        solutions_after = WorkspaceQuestionSolution.query.count()
        attempts_after = WorkspaceQuestionAttempt.query.count()
        followups_after = WorkspaceQuestionFollowUp.query.count()

        print("PENDING TRANSACTION VERIFICATION")
        print("--------------------------------")
        print(f"Questions deleted:   {deleted_questions}")
        print(f"Solutions deleted:  {deleted_solutions}")
        print(f"Attempts deleted:   {deleted_attempts}")
        print(f"Follow-ups deleted: {deleted_followups}")
        print("")
        print(f"Ordinary QuestionsNScore: {ordinary_after}")
        print(f"Workspace questions:      {questions_after}")
        print(f"Workspace solutions:      {solutions_after}")
        print(f"Workspace attempts:       {attempts_after}")
        print(f"Workspace follow-ups:     {followups_after}")
        print("")

        # Ordinary questions MUST be completely unchanged.
        if ordinary_after != ordinary_before:
            raise RuntimeError(
                "SAFETY FAILURE: QuestionsNScore count changed. "
                "Transaction will be rolled back."
            )

        # Every workspace-question-related table must be empty.
        if any(
            value != 0
            for value in (
                questions_after,
                solutions_after,
                attempts_after,
                followups_after,
            )
        ):
            raise RuntimeError(
                "SAFETY FAILURE: Workspace question data remains. "
                "Transaction will be rolled back."
            )

        db.session.commit()

        print("================================================")
        print(" CLEANUP COMMITTED SUCCESSFULLY")
        print("================================================")
        print("")
        print("Ordinary QuestionsNScore was unchanged.")
        print("All workspace questions and their related data were removed.")
        print("")

    except Exception:
        db.session.rollback()

        print("")
        print("================================================")
        print(" CLEANUP ROLLED BACK")
        print("================================================")
        print("")
        print("NO database changes were committed.")
        print("")

        raise
