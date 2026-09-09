import pytest
from flask import Flask

from database.db import db
from database.models import (
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceSettings,
    WorkspaceQuestion,
    WorkspaceQuestionSolution,
)
from services.workspace_computation_service import WorkspaceComputationService


@pytest.fixture
def test_app(tmp_path):
    app = Flask(__name__)

    db_path = tmp_path / "workspace_wolfram_test.sqlite"

    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {
            "check_same_thread": False,
            "timeout": 10,
        }
    }

    db.init_app(app)

    with app.app_context():
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_workspace_real_wolfram(test_app):

    with test_app.app_context():

        # ---------------------------------------------------------
        # Create workspace data
        # ---------------------------------------------------------

        user = User(
            username="wolfram_test_user",
            password="test-password",
        )

        db.session.add(user)
        db.session.flush()

        workspace = Workspace(
            name="Wolfram Test Workspace",
            join_code="WOLFRAMTEST123",
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
        )

        question = WorkspaceQuestion(
            workspace_id=workspace.id,
            author_id=user.id,
            question="Integrate[x^2, x]",
            visibility="public",
            status="active",
        )

        db.session.add_all([
            member,
            settings,
            question,
        ])

        db.session.commit()

        user_id = user.id
        workspace_id = workspace.id
        question_id = question.id

        # ---------------------------------------------------------
        # Run REAL workspace computation
        # ---------------------------------------------------------

        service = WorkspaceComputationService()

        result, error = service.compute_question(
            user_id=user_id,
            workspace_id=workspace_id,
            question_id=question_id,
            operation="compute",
            provider="wolfram",
        )

        print("\n=== REAL WOLFRAM TEST ===")
        print("Result:")
        print(result)
        print("\nError:")
        print(error)

        # ---------------------------------------------------------
        # Basic assertions
        # ---------------------------------------------------------

        assert error is None
        assert result is not None

        assert result["status"] == "completed"
        assert result["cached"] is False
        assert result["workspace_question_id"] == question_id

        # The engine should be Wolfram.
        assert result["engine"] == "wolfram"

        # ---------------------------------------------------------
        # Verify persisted database result
        # ---------------------------------------------------------

        solution = (
            WorkspaceQuestionSolution.query
            .filter_by(workspace_question_id=question_id)
            .first()
        )

        assert solution is not None
        assert solution.status == "completed"
        assert solution.engine == "wolfram"
        assert solution.result_json is not None

        print("\n=== DATABASE SOLUTION ===")
        print("Solution ID:", solution.id)
        print("Engine:", solution.engine)
        print("Status:", solution.status)
        print("Stored result:", solution.result_json)

        # ---------------------------------------------------------
        # Second call must use cache
        # ---------------------------------------------------------

        cached_result, cached_error = service.compute_question(
            user_id=user_id,
            workspace_id=workspace_id,
            question_id=question_id,
            operation="compute",
            provider="wolfram",
        )

        print("\n=== CACHE TEST ===")
        print("Cached result:")
        print(cached_result)
        print("Cached error:")
        print(cached_error)

        assert cached_error is None
        assert cached_result is not None
        assert cached_result["status"] == "completed"
        assert cached_result["cached"] is True
        assert cached_result["solution_id"] == result["solution_id"]