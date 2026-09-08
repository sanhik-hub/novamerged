from database.db import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)


class QuestionsNScore(db.Model):
    __tablename__ = "questionsNScore"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    user_question = db.Column(db.Text, nullable=False)
    ai_questions = db.Column(db.Text, nullable=False)
    ai_answers = db.Column(db.Text, nullable=False)
    wrong_answered_question = db.Column(db.Text, nullable=True)
    score = db.Column(db.String(80), nullable=True)


# ============================================================
# WORKSPACES
# ============================================================

class Workspace(db.Model):
    __tablename__ = "workspaces"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(120),
        nullable=False
    )

    join_code = db.Column(
        db.String(32),
        nullable=False,
        unique=True,
        index=True
    )

    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now()
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="active"
    )


class WorkspaceMember(db.Model):
    __tablename__ = "workspace_members"

    id = db.Column(db.Integer, primary_key=True)

    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("workspaces.id"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="member"
    )

    joined_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now()
    )

    __table_args__ = (
        db.UniqueConstraint(
            "workspace_id",
            "user_id",
            name="unique_workspace_member"
        ),
    )


class WorkspaceSettings(db.Model):
    __tablename__ = "workspace_settings"

    id = db.Column(db.Integer, primary_key=True)

    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("workspaces.id"),
        nullable=False,
        unique=True
    )

    # "offline" for local computational engines.
    # "online" will later allow internet/Wolfram online access.
    computation_mode = db.Column(
        db.String(20),
        nullable=False,
        default="offline"
    )

    # Whether normal members may post questions.
    allow_member_posting = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    # Whether normal members may solve questions
    # inside this workspace.
    allow_member_solving = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )


class WorkspaceQuestion(db.Model):
    __tablename__ = "workspace_questions"

    id = db.Column(db.Integer, primary_key=True)

    workspace_id = db.Column(
        db.Integer,
        db.ForeignKey("workspaces.id"),
        nullable=False
    )

    author_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    question = db.Column(
        db.Text,
        nullable=False
    )

    image_path = db.Column(
        db.Text,
        nullable=True
    )

    # "solver" = ordinary workspace problem
    # "assessment" = controlled MCQ/test session
    question_type = db.Column(
        db.String(20),
        nullable=False,
        default="solver"
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.now()
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="active"
    )