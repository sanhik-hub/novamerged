import json
import time
import uuid
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError

from database.db import db
from database.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceQuestion,
    WorkspaceSettings,
    WorkspaceQuestionSolution,
)

from services.computation_service import ComputationService


class WorkspaceComputationService:
    """
    Workspace-level computation service.

    Guarantees that a workspace question has at most one active
    computation at a time.

    Successful computations are cached permanently.

    Failed computations are recorded as failed state, but are NOT
    treated as valid cached solutions. A later request may retry them.
    """

    COMPUTATION_WAIT_SECONDS = 60
    POLL_INTERVAL_SECONDS = 0.25

    def __init__(self):
        self.computation = ComputationService()

    # =========================================================
    # PUBLIC COMPUTATION
    # =========================================================

    def compute_question(
        self,
        user_id: int,
        workspace_id: int,
        question_id: int,
        operation: str = "compute",
        provider: str = "gemini",
    ):
        workspace = Workspace.query.filter_by(
            id=workspace_id,
            status="active",
        ).first()

        if not workspace:
            return None, "Workspace not found"

        membership = WorkspaceMember.query.filter_by(
            workspace_id=workspace_id,
            user_id=user_id,
        ).first()

        if not membership:
            return None, "You are not a member of this workspace"

        question = WorkspaceQuestion.query.filter_by(
            id=question_id,
            workspace_id=workspace_id,
            status="active",
        ).first()

        if not question:
            return None, "Workspace question not found"

        # -----------------------------------------------------
        # Private-question access
        # -----------------------------------------------------

        if (
            question.visibility == "private"
            and membership.role != "admin"
            and question.author_id != user_id
        ):
            return None, "Workspace question not found"

        # -----------------------------------------------------
        # Workspace computation settings
        # -----------------------------------------------------

        settings = WorkspaceSettings.query.filter_by(
            workspace_id=workspace_id
        ).first()

        if not settings:
            return None, "Workspace settings not found"

        # Workspace computation is online-only.
        # The frontend does not expose a computation-mode selector.

        # -----------------------------------------------------
        # Existing successful solution
        # -----------------------------------------------------

        cached = WorkspaceQuestionSolution.query.filter_by(
            workspace_question_id=question.id
        ).first()

        solution = None

        if cached and cached.status == "completed":
            if cached.engine == provider:
                result = self._decode_result(cached.result_json)

                return {
                    "cached": True,
                    "solution_id": cached.id,
                    "workspace_question_id": question.id,
                    "engine": cached.engine,
                    "status": cached.status,
                    "result": result,
                    "error_message": cached.error_message,
                }, None

            # A completed solution from another provider is stale.
            # Reuse the existing row and recompute with the current
            # Workspace provider.
            cached.engine = provider
            cached.status = "computing"
            cached.result_json = None
            cached.error_message = None
            solution = cached

            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                return None, "Unable to reset stale workspace solution"

        # -----------------------------------------------------
        # Existing computation in progress
        # -----------------------------------------------------

        if cached and cached.status == "computing":
            return self._wait_for_computation(
                question_id=question.id,
            )

        # -----------------------------------------------------
        # Failed state
        #
        # A failed computation is NOT a valid cache.
        #
        # Remove the old failure state so this request can attempt
        # a fresh computation.
        # -----------------------------------------------------

        if cached and cached.status == "failed":
            try:
                db.session.delete(cached)
                db.session.commit()
            except Exception:
                db.session.rollback()

        # -----------------------------------------------------
        # Claim the computation
        # -----------------------------------------------------
        #
        # The unique constraint on workspace_question_id ensures
        # only one request can successfully create the computing
        # row.
        #
        # If another request wins the race, IntegrityError is
        # raised and this request waits for that computation.
        # -----------------------------------------------------

        computation_token = uuid.uuid4().hex

        try:
            if solution is None:
                solution = WorkspaceQuestionSolution(
                    workspace_question_id=question.id,
                    engine=provider,
                    status="computing",
                    result_json=None,
                    error_message=None,
                )

                db.session.add(solution)
                db.session.commit()

        except IntegrityError:
            db.session.rollback()

            # Another request claimed this question between our
            # cache lookup and INSERT.
            return self._wait_for_computation(
                question_id=question.id,
            )

        except Exception as exc:
            db.session.rollback()

            return None, (
                f"Failed to claim workspace computation: {exc}"
            )

        # -----------------------------------------------------
        # We are the sole computation owner.
        # -----------------------------------------------------

        try:
            result = self.computation.compute(
                query=question.question,
                operation=operation,
                provider=provider,
                image_path=question.image_path,
            )

            engine = result.get("engine") or provider

            if result.get("success"):
                serializable_result = self._make_json_safe(result)

                solution.engine = engine
                solution.status = "completed"
                solution.result_json = json.dumps(
                    serializable_result,
                    ensure_ascii=False,
                )
                solution.error_message = None

                db.session.commit()

                return {
                    "cached": False,
                    "solution_id": solution.id,
                    "workspace_question_id": question.id,
                    "engine": solution.engine,
                    "status": solution.status,
                    "result": serializable_result,
                    "error_message": None,
                }, None

            # -------------------------------------------------
            # Failed computation
            # -------------------------------------------------
            #
            # Keep the row as failed state so waiting requests
            # can see that the computation finished unsuccessfully.
            #
            # It is NOT considered a cache because only
            # status="completed" is returned as cached above.
            # -------------------------------------------------

            safe_result = self._make_json_safe(result)

            solution.engine = engine
            solution.status = "failed"
            solution.result_json = json.dumps(
                safe_result,
                ensure_ascii=False,
            )
            solution.error_message = result.get("error")

            db.session.commit()

            return {
                "cached": False,
                "solution_id": solution.id,
                "workspace_question_id": question.id,
                "engine": engine,
                "status": "failed",
                "result": safe_result,
                "error_message": result.get("error"),
            }, None

        except Exception as exc:
            # -------------------------------------------------
            # Unexpected computation failure
            # -------------------------------------------------

            db.session.rollback()

            # Re-fetch because rollback expires the object.
            failed_solution = WorkspaceQuestionSolution.query.filter_by(
                workspace_question_id=question.id
            ).first()

            if failed_solution:
                failed_solution.status = "failed"
                failed_solution.error_message = str(exc)

                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            return {
                "cached": False,
                "solution_id": (
                    failed_solution.id
                    if failed_solution
                    else None
                ),
                "workspace_question_id": question.id,
                "engine": provider,
                "status": "failed",
                "result": None,
                "error_message": str(exc),
            }, None

    # =========================================================
    # WAIT FOR EXISTING COMPUTATION
    # =========================================================

    def _wait_for_computation(self, question_id: int):
        """
        Wait for another request that currently owns the
        computation.

        The waiting request never invokes the computation engine.
        It only observes the database state.
        """

        deadline = (
            time.monotonic()
            + self.COMPUTATION_WAIT_SECONDS
        )

        while time.monotonic() < deadline:
            # Make sure the current SQLAlchemy session sees fresh
            # database state.
            db.session.expire_all()

            solution = WorkspaceQuestionSolution.query.filter_by(
                workspace_question_id=question_id
            ).first()

            if solution is None:
                # The worker disappeared before creating a final
                # state. Give the caller a clear response rather
                # than invoking the engine itself.
                return {
                    "cached": False,
                    "solution_id": None,
                    "workspace_question_id": question_id,
                    "engine": None,
                    "status": "failed",
                    "result": None,
                    "error_message": (
                        "Workspace computation ended unexpectedly."
                    ),
                }, None

            if solution.status == "completed":
                result = self._decode_result(
                    solution.result_json
                )

                return {
                    "cached": True,
                    "solution_id": solution.id,
                    "workspace_question_id": question_id,
                    "engine": solution.engine,
                    "status": "completed",
                    "result": result,
                    "error_message": solution.error_message,
                }, None

            if solution.status == "failed":
                result = self._decode_result(
                    solution.result_json
                )

                return {
                    "cached": False,
                    "solution_id": solution.id,
                    "workspace_question_id": question_id,
                    "engine": solution.engine,
                    "status": "failed",
                    "result": result,
                    "error_message": solution.error_message,
                }, None

            time.sleep(self.POLL_INTERVAL_SECONDS)

        # -----------------------------------------------------
        # Computation exceeded the waiting period.
        # -----------------------------------------------------

        return {
            "cached": False,
            "solution_id": None,
            "workspace_question_id": question_id,
            "engine": None,
            "status": "computing",
            "result": None,
            "error_message": (
                "Computation is still in progress. "
                "Please try again shortly."
            ),
        }, None

    # =========================================================
    # JSON SERIALIZATION
    # =========================================================

    @classmethod
    def _make_json_safe(cls, value):
        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        if isinstance(value, dict):
            return {
                str(key): cls._make_json_safe(item)
                for key, item in value.items()
            }

        if isinstance(value, (list, tuple)):
            return [
                cls._make_json_safe(item)
                for item in value
            ]

        if isinstance(value, set):
            return [
                cls._make_json_safe(item)
                for item in value
            ]

        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return str(value)

    # =========================================================
    # RESULT DECODING
    # =========================================================

    @staticmethod
    def _decode_result(value):
        if not value:
            return None

        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value