from database.db import db
from database.models import Admin, QuestionsNScore


def login_admin(username: str, password: str):
    try:
        admin = Admin.query.filter_by(username=username).first()
    except Exception:
        return None, "Database query failed"

    if not admin:
        return None, "Username not found"

    if admin.password != password:
        return None, "Incorrect password"

    return admin, None


def get_admin_user_history(
    admin_username: str,
    admin_password: str,
    student_username: str,
):
    admin, error = login_admin(admin_username, admin_password)
    if error or not admin:
        return None, error or "Invalid admin session"

    try:
        entries = QuestionsNScore.query.filter_by(
            username=student_username
        ).order_by(QuestionsNScore.id.desc()).all()

        return [
            {
                "id": entry.id,
                "user_question": entry.user_question,
                "score": entry.score,
            }
            for entry in entries
        ], None

    except Exception as exc:
        return None, f"Database query failed: {exc}"


def get_admin_history_detail(
    admin_username: str,
    admin_password: str,
    student_username: str,
    history_id: int,
):
    admin, error = login_admin(admin_username, admin_password)
    if error or not admin:
        return None, error or "Invalid admin session"

    try:
        entry = QuestionsNScore.query.filter_by(
            id=history_id,
            username=student_username,
        ).first()

        if not entry:
            return None, "History entry not found"

        return {
            "id": entry.id,
            "user_question": entry.user_question,
            "ai_questions": entry.ai_questions,
            "ai_answers": entry.ai_answers,
            "score": entry.score,
            "wrong_answered_question": entry.wrong_answered_question,
            "remarks": entry.remarks,
        }, None

    except Exception as exc:
        return None, f"Database query failed: {exc}"
