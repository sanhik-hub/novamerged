import json
from datetime import datetime, timezone

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

from services.execution_service import ExecutionService
from services.language import ConversationContext


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

    if mode not in {"solver", "assessment", "mcq", "guided"}:
        return None, "Invalid attempt mode"

    attempt = WorkspaceQuestionAttempt(
        workspace_question_id=question.id,
        user_id=user.id,
        mode=mode,
        status="active",
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
        "status": attempt.status,
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

    if attempt.status != "active":
        return None, "Workspace question attempt is no longer active"
    attempt.result_json = (
        json.dumps(result, ensure_ascii=False)
        if result is not None
        else None
    )

    attempt.score = score
    attempt.solution_revealed = bool(solution_revealed)
    attempt.completed_at = datetime.now(timezone.utc)
    attempt.status = "completed"

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
        "status": attempt.status,
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

    solution = WorkspaceQuestionSolution.query.filter_by(
        workspace_question_id=question.id,
    ).first()

    solution_result = None
    solution_steps = []

    if solution and solution.result_json:
        try:
            parsed_solution = (
                solution.result_json
                if isinstance(solution.result_json, dict)
                else json.loads(solution.result_json)
            )

            if isinstance(parsed_solution, dict):
                solution_result = parsed_solution

                steps = parsed_solution.get("steps")
                if isinstance(steps, list):
                    solution_steps = steps

                user_question = parsed_solution.get("user_question")
                if isinstance(user_question, dict):
                    if "solution" in user_question and solution_result is not None:
                        solution_result = parsed_solution

        except (TypeError, ValueError, json.JSONDecodeError):
            solution_result = solution.result_json

    context = ConversationContext(
        problem_text=question.question,
        current_result=solution_result,
        steps=solution_steps,
    )

    try:
        execution = ExecutionService().execute(
            followup_question,
            context=context,
        )
    except Exception as exc:
        return None, f"Failed to process follow-up: {exc}"

    if not execution.success:
        return None, execution.error or "Failed to process follow-up"

    generated_answer = execution.answer
    generated_engine = execution.provider or engine or "local_llm"

    followup = WorkspaceQuestionFollowUp(
        workspace_question_id=question.id,
        user_id=user.id,
        question=followup_question,
        answer=generated_answer,
        engine=generated_engine,
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
            "status": attempt.status,
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


def get_workspace_member_performance(
    username: str,
    workspace_id: int,
    member_user_id: int,
):
    user, membership, error = _get_workspace_member(
        username,
        workspace_id,
    )

    if error:
        return None, error

    if membership.role not in {"owner", "admin"}:
        return None, "Only workspace owners and admins can view member performance."

    target_user = User.query.filter_by(id=member_user_id).first()

    if target_user is None:
        return None, "User not found."

    target_membership = WorkspaceMember.query.filter_by(
        workspace_id=workspace_id,
        user_id=member_user_id,
    ).first()

    if target_membership is None:
        return None, "User is not a member of this workspace."

    attempts = (
        WorkspaceQuestionAttempt.query
        .join(
            WorkspaceQuestion,
            WorkspaceQuestion.id == WorkspaceQuestionAttempt.workspace_question_id,
        )
        .filter(
            WorkspaceQuestion.workspace_id == workspace_id,
            WorkspaceQuestionAttempt.user_id == member_user_id,
        )
        .order_by(
            WorkspaceQuestionAttempt.started_at.asc()
        )
        .all()
    )

    if not attempts:
        return [], None

    question_ids = {
        attempt.workspace_question_id
        for attempt in attempts
        if attempt.workspace_question_id is not None
    }

    questions = (
        WorkspaceQuestion.query
        .filter(WorkspaceQuestion.id.in_(question_ids))
        .all()
    )

    question_by_id = {
        question.id: question
        for question in questions
    }

    performance = []

    for attempt in attempts:
        question = question_by_id.get(
            attempt.workspace_question_id
        )

        result = None

        if attempt.result_json:
            try:
                result = json.loads(attempt.result_json)
            except (TypeError, ValueError):
                result = None

        correct_count = None
        total_count = None
        score_label = None
        score_percent = None

        if isinstance(result, dict):
            questions_data = result.get("questions")

            if isinstance(questions_data, list):
                total_count = len(questions_data)

            raw_correct = result.get("correct")

            if isinstance(raw_correct, (int, float)):
                correct_count = int(raw_correct)

            if (
                correct_count is None
                and total_count
                and isinstance(result.get("answers"), dict)
            ):
                computed_correct = 0

                for index, question_data in enumerate(questions_data):
                    if not isinstance(question_data, dict):
                        continue

                    correct_option = question_data.get("correct_option")
                    submitted_option = result["answers"].get(str(index))

                    if (
                        isinstance(correct_option, int)
                        and isinstance(submitted_option, int)
                        and correct_option == submitted_option
                    ):
                        computed_correct += 1

                correct_count = computed_correct

        if (
            isinstance(correct_count, int)
            and isinstance(total_count, int)
            and total_count > 0
        ):
            correct_count = max(0, min(correct_count, total_count))
            score_label = f"{correct_count}/{total_count}"
            score_percent = round(
                (correct_count / total_count) * 100,
                2,
            )
        elif isinstance(attempt.score, (int, float)):
            score_label = str(attempt.score)

        performance.append(
            {
                "id": attempt.id,
                "workspace_question_id": attempt.workspace_question_id,
                "question": (
                    question.question
                    if question is not None
                    else None
                ),
                "image_path": (
                    question.image_path
                    if question is not None
                    else None
                ),
                "question_type": (
                    question.question_type
                    if question is not None
                    else None
                ),
                "user_id": attempt.user_id,
                "username": target_user.username,
                "mode": attempt.mode,
                "status": attempt.status,
                "submitted_answer": attempt.submitted_answer,
                "result": result,
                "score": attempt.score,
                "correct_count": correct_count,
                "total_count": total_count,
                "score_label": score_label,
                "score_percent": score_percent,
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
        )

    return performance, None
def _close_workspace_question_attempt(
    username: str,
    workspace_id: int,
    attempt_id: int,
    status: str,
):
    user, membership, error = _get_workspace_member(
        username,
        workspace_id,
    )

    if error:
        return None, error

    if status not in {"exited", "terminated"}:
        return None, "Invalid attempt status"

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

    if attempt.status != "active":
        return None, "Workspace question attempt is no longer active"

    attempt.status = status
    attempt.completed_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None, "Failed to update workspace question attempt"

    return {
        "id": attempt.id,
        "workspace_question_id": attempt.workspace_question_id,
        "user_id": attempt.user_id,
        "mode": attempt.mode,
        "status": attempt.status,
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
    }, None


def exit_workspace_question_attempt(
    username: str,
    workspace_id: int,
    attempt_id: int,
):
    return _close_workspace_question_attempt(
        username=username,
        workspace_id=workspace_id,
        attempt_id=attempt_id,
        status="exited",
    )


def terminate_workspace_question_attempt(
    username: str,
    workspace_id: int,
    attempt_id: int,
):
    return _close_workspace_question_attempt(
        username=username,
        workspace_id=workspace_id,
        attempt_id=attempt_id,
        status="terminated",
    )

