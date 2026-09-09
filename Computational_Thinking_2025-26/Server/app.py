import os
from dotenv import load_dotenv
from flask import Flask
from database.db import db
from database.models import (
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceSettings,
    WorkspaceQuestion,
    WorkspaceInvitation,
    WorkspaceQuestionSolution,
    WorkspaceQuestionAttempt,
    WorkspaceQuestionFollowUp,
)
from routes.routes import register_routes
from flask_cors import CORS

load_dotenv()
secret_key = os.getenv("SECRET_KEY")

if not secret_key:
    raise RuntimeError(
        "SECRET_KEY is not configured in the environment."
    )
app = Flask(__name__)
app.config["SECRET_KEY"] = secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_timeout": 30,
    "connect_args": {"connect_timeout": 10},
}
CORS(
    app,
    resources={r"\*": {"origins": "*"}},
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

db.init_app(app)

register_routes(app)

try:
    with app.app_context():
        db.create_all()
except Exception as e:
    print(f"Error creating database tables: {e}")

if __name__ == "__main__":
    app.run(debug=False)