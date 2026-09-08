from services.workspace_services import (
    create_workspace,
    join_workspace,
    get_user_workspaces,
    get_workspace_details,
    leave_workspace,
)
from services.auth_services import (
    create_auth_token,
    verify_auth_token,
    get_bearer_token,
)
import math

from flask import request

from services.user_services import create_user, login_user
from services.questionAPI import get_Doubtresponse, get_response
from services.score_services import add_ScoreDB
from services.graphical_question import get_graphical_response
from services.history_services import get_user_history, get_history_detail


def is_valid_coordinates(value):
    if not isinstance(value, list) or len(value) > 4:
        return False

    for point in value:
        if not isinstance(point, list) or len(point) != 2:
            return False

        if not all(
            isinstance(coordinate, (int, float))
            and math.isfinite(coordinate)
            for coordinate in point
        ):
            return False

    return True

def get_authenticated_user():
    token = get_bearer_token(request)

    if not token:
        return None, (
            {
                "error": "Authentication required"
            },
            401,
        )

    user, error = verify_auth_token(token)

    if error:
        return None, (
            {
                "error": error
            },
            401,
        )

    return user, None

def register_routes(app):

    @app.route("/")
    def home():
        return {
            "message": "Backend is running"
        }

    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok"}, 200

    # -------------------------
    # CREATE NEW USER
    # -------------------------

    @app.route("/NewUser_login", methods=["POST"])
    def receive_NewUser_data():

        NewUserdata = request.get_json(silent=True) or {}

        if not isinstance(NewUserdata, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username",
            "NewPassword"
        }

        allowed_fields = required_fields

        missing_fields = required_fields - NewUserdata.keys()
        extra_fields = set(NewUserdata.keys()) - allowed_fields

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        if extra_fields:
            return {
                "error": f"Unexpected fields: {sorted(extra_fields)}"
            }, 400

        local_username = NewUserdata["Username"]
        local_password = NewUserdata["NewPassword"]

        if (
            not isinstance(local_username, str)
            or not isinstance(local_password, str)
        ):
            return {
                "error": "Username and NewPassword must both be strings"
            }, 400

        user, error = create_user(
            local_username,
            local_password
        )

        if error == "Username already exists":
            return {
                "error": error
            }, 409

        if error == "Database query failed":
            return {
                "error": error
            }, 500

        if error == "Failed to create user":
            return {
                "error": error
            }, 500
        token = create_auth_token(user)
        return {
            "message": "User created successfully",
            "data": {
                "id": user.id,
                "username": user.username,
                "token": token,
            },
        }, 201

    # -------------------------
    # LOGIN EXISTING USER
    # -------------------------

    @app.route("/Old_User_login", methods=["POST"])
    def receive_OldUser_data():

        Userdata = request.get_json(silent=True) or {}

        if not isinstance(Userdata, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username",
            "Password"
        }

        missing_fields = required_fields - Userdata.keys()

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        local_username = Userdata.get("Username")
        local_password = Userdata.get("Password")

        if (
            not isinstance(local_username, str)
            or not isinstance(local_password, str)
        ):
            return {
                "error": "Username and Password must both be strings"
            }, 400

        user, error = login_user(
            local_username,
            local_password
        )

        if error == "Database query failed":
            return {
                "error": error
            }, 500

        if error == "Username not found":
            return {
                "error": error
            }, 404

        if error == "Incorrect password":
            return {
                "error": error
            }, 401
        
        token = create_auth_token(user)
        return {
            "message": "Login successful",
            "data": {
                "id": user.id,
                "username": user.username,
                "token": token
            },
        }, 200

    # -------------------------
    # POST STANDARD QUESTION
    # -------------------------

    @app.route("/QuestionPost", methods=["POST"])
    def receive_Question_data():

        question_data = request.get_json(silent=True) or {}

        if not isinstance(question_data, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username",
            "Question",
            "Image_path"
        }

        missing_fields = required_fields - question_data.keys()

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        username = question_data.get("Username")
        question = question_data.get("Question")
        img_path = question_data.get("Image_path")

        try:
            response = get_response(
                username,
                question,
                img_path
            )
        except Exception as e:
            return {
                "error": f"Failed to get response from Gemini API: {e}"
            }, 500

        return response, 200

    # -------------------------
    # POST GRAPHICAL QUESTION
    # -------------------------

    @app.route("/GraphicalQuestionPost", methods=["POST"])
    def receive_GraphicalQuestion_data():

        graphical_question_data = request.get_json(silent=True) or {}

        if not isinstance(graphical_question_data, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username",
            "Question",
            "Coordinates"
        }

        missing_fields = required_fields - graphical_question_data.keys()

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        username = graphical_question_data.get("Username")
        question = graphical_question_data.get("Question")
        coordinates = graphical_question_data.get("Coordinates")

        if not isinstance(username, str):
            return {
                "error": "Username must be a string"
            }, 400

        if not isinstance(question, str):
            return {
                "error": "Question must be a string"
            }, 400

        if not is_valid_coordinates(coordinates):
            return {
                "error": "Coordinates must be a list containing at most 4 [x, y] coordinate pairs"
            }, 400

        try:
            response = get_graphical_response(
                username,
                question,
                coordinates
            )
        except Exception as e:
            return {
                "error": f"Failed to get graphical response from Gemini API: {e}"
            }, 500

        return response, 200

    # -------------------------
    # WRONG ANSWER / LEARN AGAIN
    # -------------------------

    @app.route("/DoubtQuestionPost", methods=["POST"])
    def receive_DoubtQuestion_data():

        doubt_question_data = request.get_json(silent=True) or {}

        if not isinstance(doubt_question_data, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username",
            "WrongAnsweredquestion",
            "QuestionJson"
        }

        missing_fields = required_fields - doubt_question_data.keys()

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        username = doubt_question_data.get("Username")
        WrongAnsweredquestion = doubt_question_data.get("WrongAnsweredquestion")
        QuestionJson = doubt_question_data.get("QuestionJson")

        try:
            response = get_Doubtresponse(
                username,
                WrongAnsweredquestion,
                QuestionJson
            )
        except Exception as e:
            return {
                "error": f"Failed to get response from Gemini API: {e}"
            }, 500

        return response, 200

    # -------------------------
    # SCORE
    # -------------------------

    @app.route("/ScorePost", methods=["POST"])
    def receive_Score_data():

        score_data = request.get_json(silent=True) or {}

        if not isinstance(score_data, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username",
            "QuestionJson",
            "wrong_answered_questions",
            "Score"
        }

        missing_fields = required_fields - score_data.keys()

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        username = score_data.get("Username")
        QuestionJson = score_data.get("QuestionJson")
        Score = score_data.get("Score")
        wrong_answered_questions = score_data.get("wrong_answered_questions")

        try:
            add_ScoreDB(
                username,
                QuestionJson,
                wrong_answered_questions,
                Score
            )
        except Exception as e:
            return {
                "error": f"Failed to add score entry: {e}"
            }, 500

        return {
            "message": "Score entry added successfully"
        }, 200

    # -------------------------
    # GET USER HISTORY
    # -------------------------

    @app.route("/GetUserHistory", methods=["POST"])
    def receive_GetUserHistory_data():

        history_data = request.get_json(silent=True) or {}

        if not isinstance(history_data, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username"
        }

        missing_fields = required_fields - history_data.keys()

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        username = history_data.get("Username")

        if not isinstance(username, str):
            return {
                "error": "Username must be a string"
            }, 400

        history, error = get_user_history(username)

        if error:
            return {
                "error": error
            }, 500

        return {
            "message": "History retrieved successfully",
            "data": history
        }, 200

    # -------------------------
    # GET HISTORY DETAIL
    # -------------------------

    @app.route("/GetHistoryDetail", methods=["POST"])
    def receive_GetHistoryDetail_data():

        history_detail_data = request.get_json(silent=True) or {}

        if not isinstance(history_detail_data, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username",
            "HistoryId"
        }

        missing_fields = required_fields - history_detail_data.keys()

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        username = history_detail_data.get("Username")
        history_id = history_detail_data.get("HistoryId")

        if not isinstance(username, str):
            return {
                "error": "Username must be a string"
            }, 400

        if (
            isinstance(history_id, bool)
            or not isinstance(history_id, int)
            or history_id < 1
        ):
            return {
                "error": "HistoryId must be a positive integer"
            }, 400

        history_detail, error = get_history_detail(
            history_id,
            username
        )

        if error == "History entry not found":
            return {
                "error": error
            }, 404

        if error:
            return {
                "error": error
            }, 500

        return {
            "message": "History detail retrieved successfully",
            "data": history_detail
        }, 200
        # ============================================================
    # CREATE WORKSPACE
    # ============================================================

    @app.route("/WorkspaceCreate", methods=["POST"])
    def receive_WorkspaceCreate():
        user, auth_error = get_authenticated_user()

        if auth_error:
            return auth_error

        workspace_data = request.get_json(silent=True) or {}

        if not isinstance(workspace_data, dict):
            return {"error": "Invalid JSON payload"}, 400

        required_fields = {"Name"}
        missing_fields = required_fields - workspace_data.keys()
        extra_fields = set(workspace_data.keys()) - required_fields

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        if extra_fields:
            return {
                "error": f"Unexpected fields: {sorted(extra_fields)}"
            }, 400

        name = workspace_data.get("Name")

        if not isinstance(name, str):
            return {
                "error": "Name must be a string"
            }, 400

        workspace, error = create_workspace(
            user.username,
            name,
        )

        if error == "User not found":
            return {"error": error}, 404

        if error:
            return {"error": error}, 400

        return {
            "message": "Workspace created successfully",
            "data": workspace,
        }, 201

    # ============================================================
    # JOIN WORKSPACE
    # ============================================================

    @app.route("/WorkspaceJoin", methods=["POST"])
    def receive_WorkspaceJoin_data():
        data = request.get_json(silent=True) or {}

        if not isinstance(data, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username",
            "JoinCode",
        }

        missing_fields = required_fields - data.keys()

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        username = data.get("Username")
        join_code = data.get("JoinCode")

        if not isinstance(username, str):
            return {
                "error": "Username must be a string"
            }, 400

        if not isinstance(join_code, str):
            return {
                "error": "JoinCode must be a string"
            }, 400

        workspace, error = join_workspace(
            username,
            join_code,
        )

        if error == "User not found":
            return {
                "error": error
            }, 404

        if error == "Invalid workspace join code":
            return {
                "error": error
            }, 404

        if error == "User is already a member of this workspace":
            return {
                "error": error
            }, 409

        if error:
            return {
                "error": error
            }, 500

        return {
            "message": "Joined workspace successfully",
            "data": workspace,
        }, 200


    # ============================================================
    # GET USER WORKSPACES
    # ============================================================

    @app.route("/Workspaces", methods=["POST"])
    def receive_Workspaces_data():
        data = request.get_json(silent=True) or {}

        if not isinstance(data, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        if "Username" not in data:
            return {
                "error": "Missing fields: ['Username']"
            }, 400

        username = data.get("Username")

        if not isinstance(username, str):
            return {
                "error": "Username must be a string"
            }, 400

        workspaces, error = get_user_workspaces(username)

        if error == "User not found":
            return {
                "error": error
            }, 404

        if error:
            return {
                "error": error
            }, 500

        return {
            "message": "Workspaces retrieved successfully",
            "data": workspaces,
        }, 200


    # ============================================================
    # WORKSPACE DETAILS
    # ============================================================

    @app.route("/WorkspaceDetails", methods=["POST"])
    def receive_WorkspaceDetails_data():
        data = request.get_json(silent=True) or {}

        if not isinstance(data, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username",
            "WorkspaceId",
        }

        missing_fields = required_fields - data.keys()

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        username = data.get("Username")
        workspace_id = data.get("WorkspaceId")

        if not isinstance(username, str):
            return {
                "error": "Username must be a string"
            }, 400

        if (
            isinstance(workspace_id, bool)
            or not isinstance(workspace_id, int)
            or workspace_id < 1
        ):
            return {
                "error": "WorkspaceId must be a positive integer"
            }, 400

        workspace, error = get_workspace_details(
            username,
            workspace_id,
        )

        if error in {
            "User not found",
            "Workspace not found",
        }:
            return {
                "error": error
            }, 404

        if error == "You are not a member of this workspace":
            return {
                "error": error
            }, 403

        if error:
            return {
                "error": error
            }, 500

        return {
            "message": "Workspace details retrieved successfully",
            "data": workspace,
        }, 200


    # ============================================================
    # LEAVE WORKSPACE
    # ============================================================

    @app.route("/WorkspaceLeave", methods=["POST"])
    def receive_WorkspaceLeave_data():
        data = request.get_json(silent=True) or {}

        if not isinstance(data, dict):
            return {
                "error": "Invalid JSON payload"
            }, 400

        required_fields = {
            "Username",
            "WorkspaceId",
        }

        missing_fields = required_fields - data.keys()

        if missing_fields:
            return {
                "error": f"Missing fields: {sorted(missing_fields)}"
            }, 400

        username = data.get("Username")
        workspace_id = data.get("WorkspaceId")

        if not isinstance(username, str):
            return {
                "error": "Username must be a string"
            }, 400

        if (
            isinstance(workspace_id, bool)
            or not isinstance(workspace_id, int)
            or workspace_id < 1
        ):
            return {
                "error": "WorkspaceId must be a positive integer"
            }, 400

        result, error = leave_workspace(
            username,
            workspace_id,
        )

        if error == "User not found":
            return {
                "error": error
            }, 404

        if error == "You are not a member of this workspace":
            return {
                "error": error
            }, 403

        if error and "admins cannot leave" in error:
            return {
                "error": error
            }, 403

        if error:
            return {
                "error": error
            }, 500

        return {
            "message": "Left workspace successfully",
            "data": result,
        }, 200