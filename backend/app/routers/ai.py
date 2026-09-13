import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models as m
from app.ai.client import MODEL_FAST, generate_text
from app.ai.context import lesson_prose_excerpt
from app.ai.prompts import select_text_panel_prompt
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


class AskRequest(BaseModel):
    lesson_id: str
    selected_text: str
    message: str
    conversation_id: str | None = None


@router.post("/ask")
def ask(payload: AskRequest, db: Session = Depends(get_db)):
    """docs/API.md / docs/PROMPTS.md section 7. The three shortcut buttons on
    the frontend are ordinary messages with canned text — nothing here cases
    on what `message` says.

    `conversation_id` null starts a new thread, scoped to one lesson and one
    selected passage (AIConversation); passing it back replays the thread's
    prior turns as history so follow-ups stay anchored to the same passage
    without repeating it in every message.
    """
    lesson = db.get(m.Lesson, payload.lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    if payload.conversation_id:
        conversation = db.get(m.AIConversation, payload.conversation_id)
        if not conversation or conversation.lesson_id != payload.lesson_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = m.AIConversation(
            lesson_id=payload.lesson_id, selected_text=payload.selected_text
        )
        db.add(conversation)
        db.flush()  # populates conversation.id for the messages below

    history = [{"role": msg.role, "content": msg.content} for msg in conversation.messages]

    system_instruction = select_text_panel_prompt(
        selected_text=conversation.selected_text,
        lesson_excerpt=lesson_prose_excerpt(lesson),
    )

    try:
        reply = generate_text(
            payload.message,
            history=history,
            system_instruction=system_instruction,
            model=MODEL_FAST,
        )
    except Exception:
        logger.warning("AI panel: generate_text raised", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=503, detail="AI is temporarily unavailable — try again in a moment."
        )

    db.add(m.AIMessage(conversation_id=conversation.id, role="user", content=payload.message))
    db.add(m.AIMessage(conversation_id=conversation.id, role="assistant", content=reply))
    db.commit()

    return {"conversation_id": conversation.id, "reply": reply}
