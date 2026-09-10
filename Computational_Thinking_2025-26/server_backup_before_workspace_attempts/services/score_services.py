from database.db import db
from database.models import User
from database.models import QuestionsNScore
import json

def add_ScoreDB(username, QuestionJson, wrong_answered_questions, Score):
    # Create a new QuestionsNScore instance
    data=json.loads(QuestionJson)
    
    ai_questions = data["ai_questions"]

    # Questions and answers in the same order
    ai_questions_text = ", ".join(q["question"] for q in ai_questions)
    ai_answers = ", ".join(q["options"][q["correct_option"] - 1]for q in data["ai_questions"])

    # Single user question
    user_question = data["user_question"]["question"]

    
    new_entry = QuestionsNScore(
        username=username,
        user_question=user_question,
        ai_questions=ai_questions_text, 
        ai_answers=ai_answers,     
        wrong_answered_question=wrong_answered_questions,
        score=Score
    )

    try:
        db.session.add(new_entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise Exception("Failed to add score entry to the database")