import json
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from database.db import db
from database.models import (
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceSettings,
    WorkspaceQuestion,
    WorkspaceQuestionSolution,
    WorkspaceQuestionAttempt,
    WorkspaceQuestionFollowUp,
)


def _get_workspace_member(username, workspace_id):
    user = User.query.filter_by(username=username).first()

    if not user:
        return None, None, "User not found"

    workspace = Workspace.query.filter_by(
        id=workspace_id,
        status="active",
    ).first()

    if not workspace:
        return None, None, "Workspace not found"

    membership = WorkspaceMember.query.filter_by(
        workspace_id=workspace_id,
        user_id=user.id,
    ).first()

    if not membership:
        return None, None, "You are not a member of this workspace"

    return user, membership, None


def _can_access_question(user, membership, question):
    if question.visibility == "private":
        return (
            membership.role == "admin"
            or question.author_id == user.id
        )

    return True


def get_cached_workspace_solution(
    username: str,
    workspace_id: int,
    question_id: int,
):
    user, membership, error = _get_workspace_member(
        username,
        workspace_id,
    )

    if error:
        return None, error

    question = WorkspaceQuestion.query.filter_by(
        id=question_id,
        workspace_id=workspace_id,
        status="active",
    ).first()

    if not question:
        return None, "Workspace question not found"

    if not _can_access_question(user, membership, question):
        return None, "Workspace question not found"

    solution = WorkspaceQuestionSolution.query.filter_by(
        workspace_question_id=question.id,
    ).first()

    if not solution:
        return None, None

    result = None

    if solution.result_json:
        try:
            result = json.loads(solution.result_json)
        except (TypeError, ValueError):
            result = solution.result_json

    return {
        "id": solution.id,
        "workspace_question_id": solution.workspace_question_id,
        "engine": solution.engine,
        "status": solution.status,
        "result": result,
        "error_message": solution.error_message,
        "created_at": (
            solution.created_at.isoformat()
            if solution.created_at
            else None
        ),
        "updated_at": (
            solution.updated_at.isoformat()
            if solution.updated_at
            else None
        ),
    }, None


def store_workspace_question_solution(
    username: str,
    workspace_id: int,
    question_id: int,
    engine: str,
    result,
):
    user, membership, error = _get_workspace_member(
        username,
        workspace_id,
    )

    if error:
        return None, error

    question = WorkspaceQuestion.query.filter_by(
        id=question_id,
        workspace_id=workspace_id,
        status="active",
    ).first()

    if not question:
        return None, "Workspace question not found"

    if not _can_access_question(user, membership, question):
        return None, "Workspace question not found"

    existing = WorkspaceQuestionSolution.query.filter_by(
        workspace_question_id=question.id,
    ).first()

    if existing:
        return {
            "id": existing.id,
            "workspace_question_id": existing.workspace_question_id,
            "engine": existing.engine,
            "status": existing.status,
            "result": (
                json.loads(existing.result_json)
                if existing.result_json
                else None
            ),
        }, None

    solution = WorkspaceQuestionSolution(
        workspace_question_id=question.id,
        engine=engine,
        status="completed",
        result_json=json.dumps(
            result,
            ensure_ascii=False,
        ),
        error_message=None,
    )

    try:
        db.session.add(solution)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

        existing = WorkspaceQuestionSolution.query.filter_by(
            workspace_question_id=question.id,
        ).first()

        if not existing:
            return None, "Failed to store workspace question solution"

        return {
            "id": existing.id,
            "workspace_question_id": existing.workspace_question_id,
            "engine": existing.engine,
            "status": existing.status,
            "result": (
                json.loads(existing.result_json)
                if existing.result_json
                else None
            ),
        }, None

    except Exception:
        db.session.rollback()
        return None, "Failed to store workspace question solution"

    return {
        "id": solution.id,
        "workspace_question_id": solution.workspace_question_id,
        "engine": solution.engine,
        "status": solution.status,
        "result": result,
    }, None


def create_workspace_question_attempt(
    username: str,
    workspace_id: int,
    question_id: int,
    mode="solver",
    submitted_answer=None,
):
    user, membership, error = _get_workspace_member(
        username,
        workspace_id,
    )

    if error:
        return None, error

    question = WorkspaceQuestion.query.filter_by(
        id=question_id,
        workspace_id=workspace_id,
        status="active",
    ).first()

    if not question:
        return None, "Workspace question not found"

    if not _can_access_question(user, membership, question):
        return None, "Workspace question not found"

    settings = WorkspaceSettings.query.filter_by(
        workspace_id=workspace_id,
    ).first()

    if not settings:
        return None, "Workspace settings not found"

    if membership.role != "admin" and not settings.allow_member_solving:
        return None, "Members are not allowed to solve questions"

    if mode not in {"solver", "assessment", "mcq"}:
        return None, "Invalid attempt mode"

    attempt = WorkspaceQuestionAttempt(
        workspace_question_id=question.id,
        user_id=user.id,
        mode=mode,
        submitted_answer=submitted_answer,
        solution_revealed=False,
    )

    try:
        db.session.add(attempt)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None, "Failed to create workspace question attempt"

    return {
        "id": attempt.id,
        "workspace_question_id": attempt.workspace_question_id,
        "user_id": attempt.user_id,
        "mode": attempt.mode,
        "submitted_answer": attempt.submitted_answer,
        "score": attempt.score,
        "solution_revealed": attempt.solution_revealed,
        "started_at": (
            attempt.started_at.isoformat()
            if attempt.started_at
            else None
        ),
        "completed_at": None,
    }, None


def complete_workspace_question_attempt(
    username: str,
    workspace_id: int,
    attempt_id: int,
    result=None,
    score=None,
    solution_revealed=False,
):
    user, membership, error = _get_workspace_member(
        username,
        workspace_id,
    )

    if error:
        return None, error

    attempt = WorkspaceQuestionAttempt.query.filter_by(
        id=attempt_id,
    ).first()

    if not attempt:
        return None, "Workspace question attempt not found"

    question = WorkspaceQuestion.query.filter_by(
        id=attempt.workspace_question_id,
        workspace_id=workspace_id,
        status="active",
    ).first()

    if not question:
        return None, "Workspace question not found"

    if not _can_access_question(user, membership, question):
        return None, "Workspace question not found"

    if attempt.user_id != user.id and membership.role != "admin":
        return None, "You cannot modify this attempt"

    attempt.result_json = (
        json.dumps(result, ensure_ascii=False)
        if result is not None
        else None
    )

    attempt.score = score
    attempt.solution_revealed = bool(solution_revealed)
    attempt.completed_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None, "Failed to complete workspace question attempt"

    return {
        "id": attempt.id,
        "workspace_question_id": attempt.workspace_question_id,
        "user_id": attempt.user_id,
        "mode": attempt.mode,
        "score": attempt.score,
        "solution_revealed": attempt.solution_revealed,
        "completed_at": (
            attempt.completed_at.isoformat()
            if attempt.completed_at
            else None
        ),
    }, None


def create_workspace_question_followup(
    username: str,
    workspace_id: int,
    question_id: int,
    followup_question: str,
    answer=None,
    engine=None,
):
    user, membership, error = _get_workspace_member(
        username,
        workspace_id,
    )

    if error:
        return None, error

    question = WorkspaceQuestion.query.filter_by(
        id=question_id,
        workspace_id=workspace_id,
        status="active",
    ).first()

    if not question:
        return None, "Workspace question not found"

    if not _can_access_question(user, membership, question):
        return None, "Workspace question not found"

    if not isinstance(followup_question, str):
        return None, "Follow-up question must be a string"

    followup_question = followup_question.strip()

    if not followup_question:
        return None, "Follow-up question cannot be empty"

    if len(followup_question) > 10000:
        return None, "Follow-up question is too long"

    followup = WorkspaceQuestionFollowUp(
        workspace_question_id=question.id,
        user_id=user.id,
        question=followup_question,
        answer=answer,
        engine=engine,
    )

    try:
        db.session.add(followup)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None, "Failed to create workspace question follow-up"

    return {
        "id": followup.id,
        "workspace_question_id": followup.workspace_question_id,
        "user_id": followup.user_id,
        "question": followup.question,
        "answer": followup.answer,
        "engine": followup.engine,
        "created_at": (
            followup.created_at.isoformat()
            if followup.created_at
            else None
        ),
    }, None


def get_workspace_question_attempts(
    username: str,
    workspace_id: int,
    question_id: int,
):
    user, membership, error = _get_workspace_member(
        username,
        workspace_id,
    )

    if error:
        return None, error

    question = WorkspaceQuestion.query.filter_by(
        id=question_id,
        workspace_id=workspace_id,
        status="active",
    ).first()

    if not question:
        return None, "Workspace question not found"

    if not _can_access_question(user, membership, question):
        return None, "Workspace question not found"

    query = WorkspaceQuestionAttempt.query.filter_by(
        workspace_question_id=question.id,
    )

    if membership.role != "admin":
        query = query.filter_by(
            user_id=user.id,
        )

    attempts = query.order_by(
        WorkspaceQuestionAttempt.started_at.desc()
    ).all()

    return [
        {
            "id": attempt.id,
            "workspace_question_id": attempt.workspace_question_id,
            "user_id": attempt.user_id,
            "mode": attempt.mode,
            "submitted_answer": attempt.submitted_answer,
            "result": (
                json.loads(attempt.result_json)
                if attempt.result_json
                else None
            ),
            "score": attempt.score,
            "solution_revealed": attempt.solution_revealed,
            "started_at": (
                attempt.started_at.isoformat()
                if attempt.started_at
                else None
            ),
            "completed_at": (
                attempt.completed_at.isoformat()
                if attempt.completed_at
                else None
            ),
        }
        for attempt in attempts
    ], None