from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models as m
from app import scoring
from app.database import get_db

router = APIRouter(prefix="/api/questions", tags=["questions"])


class AnswerRequest(BaseModel):
    answer: str


@router.post("/{question_id}/answer")
def answer_question(
    question_id: str, payload: AnswerRequest, db: Session = Depends(get_db)
):
    question = db.get(m.Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    try:
        result = scoring.answer_question(db, question, payload.answer)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    return result
