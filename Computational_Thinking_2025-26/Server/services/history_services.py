from database.db import db
from database.models import QuestionsNScore
import json

def get_user_history(username: str):
    """
    Fetch all chat history for a user
    Returns a list of history entries with id, user_question, and score
    """
    try:
        history_entries = QuestionsNScore.query.filter_by(username=username).order_by(
            QuestionsNScore.id.desc()
        ).all()
        
        result = []
        for entry in history_entries:
            result.append({
                "id": entry.id,
                "user_question": entry.user_question,
                "score": entry.score
            })
        
        return result, None
    except Exception as e:
        return None, f"Database query failed: {str(e)}"


def get_history_detail(history_id: int, username: str):
    """
    Fetch detailed information for a specific history entry
    Returns the full history data including questions, answers, and user responses
    """
    try:
        history_entry = QuestionsNScore.query.filter_by(
            id=history_id,
            username=username
        ).first()
        
        if not history_entry:
            return None, "History entry not found"
        
        # Parse the stored data
        detail = {
            "id": history_entry.id,
            "user_question": history_entry.user_question,
            "ai_questions": history_entry.ai_questions,
            "ai_answers": history_entry.ai_answers,
            "score": history_entry.score,
            "wrong_answered_question": history_entry.wrong_answered_question
        }
        
        return detail, None
    except Exception as e:
        return None, f"Database query failed: {str(e)}"
