import threading
import time

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

    # Use a REAL file-backed SQLite database.
    # Each thread gets its own connection.
    db_path = tmp_path / "workspace_lock_test.sqlite"

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


def test_workspace_computation_lock(test_app, monkeypatch):
    """
    Two simultaneous requests for the same workspace question
    must result in exactly one actual computation.
    """

    # ---------------------------------------------------------
    # Create test data in the main thread.
    # ---------------------------------------------------------

    with test_app.app_context():

        user = User(
            username="lock_test_user",
            password="test-password",
        )

        db.session.add(user)
        db.session.flush()

        workspace = Workspace(
            name="Lock Test Workspace",
            join_code="LOCKTEST123",
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
            question="2 + 2",
            visibility="public",
            status="active",
        )

        db.session.add_all([
            member,
            settings,
            question,
        ])

        db.session.commit()

        # IMPORTANT:
        # Copy only primitive IDs before leaving this context.
        user_id = user.id
        workspace_id = workspace.id
        question_id = question.id

        db.session.remove()

    # ---------------------------------------------------------
    # Fake the expensive computation.
    # The database claiming/locking logic remains REAL.
    # ---------------------------------------------------------

    computation_count = 0
    count_lock = threading.Lock()

    barrier = threading.Barrier(2)

    def fake_compute(*args, **kwargs):
        nonlocal computation_count

        with count_lock:
            computation_count += 1

        # Keep the computation alive long enough for the
        # second request to observe the "computing" state.
        time.sleep(1)

        return {
            "success": True,
            "engine": "test",
            "result": "4",
        }

    monkeypatch.setattr(
        "services.computation_service.ComputationService.compute",
        fake_compute,
    )

    results = []
    results_lock = threading.Lock()

    # ---------------------------------------------------------
    # Worker
    # ---------------------------------------------------------

    def worker():
        try:
            with test_app.app_context():

                service = WorkspaceComputationService()

                barrier.wait()

                result, error = service.compute_question(
                    user_id=user_id,
                    workspace_id=workspace_id,
                    question_id=question_id,
                    operation="compute",
                    provider="wolfram",
                )

                with results_lock:
                    results.append((result, error))

        finally:
            pass

    # ---------------------------------------------------------
    # Start both requests simultaneously.
    # ---------------------------------------------------------

    thread_a = threading.Thread(target=worker)
    thread_b = threading.Thread(target=worker)

    thread_a.start()
    thread_b.start()

    thread_a.join(timeout=15)
    thread_b.join(timeout=15)

    assert not thread_a.is_alive()
    assert not thread_b.is_alive()

    # ---------------------------------------------------------
    # Diagnostics
    # ---------------------------------------------------------

    print("\n=== LOCK TEST RESULTS ===")
    print("Computation count:", computation_count)
    print("Number of responses:", len(results))

    for i, (result, error) in enumerate(results, 1):
        print(f"\nRequest {i}:")
        print("Result:", result)
        print("Error:", error)

    # ---------------------------------------------------------
    # Assertions
    # ---------------------------------------------------------

    assert len(results) == 2

    # THE MAIN LOCK ASSERTION:
    # only one request is allowed to execute the computation.
    assert computation_count == 1

    # Both requests must ultimately succeed.
    for result, error in results:
        assert error is None
        assert result is not None
        assert result["status"] == "completed"

    # Exactly one database solution row should exist.
    with test_app.app_context():

        solutions = (
            WorkspaceQuestionSolution.query
            .filter_by(workspace_question_id=question_id)
            .all()
        )

        assert len(solutions) == 1
        assert solutions[0].status == "completed"