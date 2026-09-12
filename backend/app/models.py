"""SQLAlchemy models, matching docs/SCHEMA.md field for field.

IDs are UUID strings. Timestamps are UTC.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    source_filename: Mapped[str] = mapped_column(String, nullable=False)
    cover_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # processing | ready | failed
    processing_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    # Set once every chapter in the book is complete — see
    # app/pipeline/auto_quiz.py. Not in docs/SCHEMA.md, same extension as Quiz.
    final_quiz_id: Mapped[str | None] = mapped_column(ForeignKey("quizzes.id"), nullable=True)

    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="book", cascade="all, delete-orphan", order_by="Chapter.number"
    )
    final_quiz: Mapped["Quiz | None"] = relationship(foreign_keys=[final_quiz_id])


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(String, nullable=True)
    # Set once every lesson in the chapter is done or mastered — see
    # app/pipeline/auto_quiz.py. Not in docs/SCHEMA.md, same extension as Quiz.
    quiz_id: Mapped[str | None] = mapped_column(ForeignKey("quizzes.id"), nullable=True)

    book: Mapped["Book"] = relationship(back_populates="chapters")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan", order_by="Lesson.number"
    )
    quiz: Mapped["Quiz | None"] = relationship(foreign_keys=[quiz_id])


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # reading | practice
    concept_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    chapter: Mapped["Chapter"] = relationship(back_populates="lessons")
    blocks: Mapped[list["Block"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="Block.order"
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # prose | question
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_id: Mapped[str | None] = mapped_column(
        ForeignKey("questions.id"), nullable=True
    )

    lesson: Mapped["Lesson"] = relationship(back_populates="blocks")
    question: Mapped["Question | None"] = relationship(foreign_keys=[question_id])


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    # Nullable so a quiz-only question (generated to top up a quiz, per
    # docs/API.md's "top up with freshly generated ones") can exist without
    # belonging to any lesson — see app/quizzes.py. Every question created by
    # the normal lesson pipeline still always sets this.
    lesson_id: Mapped[str | None] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)  # mcq | open
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    correct_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hint: Mapped[str | None] = mapped_column(String, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    model_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    concept_tag: Mapped[str] = mapped_column(String, nullable=False)
    difficulty: Mapped[str] = mapped_column(String, nullable=False)  # easy | medium | hard
    source: Mapped[str] = mapped_column(String, nullable=False)  # book | ai | hybrid
    parent_question_id: Mapped[str | None] = mapped_column(
        ForeignKey("questions.id"), nullable=True
    )

    lesson: Mapped["Lesson"] = relationship(back_populates="questions")
    parent_question: Mapped["Question | None"] = relationship(
        remote_side=[id], foreign_keys=[parent_question_id]
    )


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False
    )  # not_started | in_progress | done | mastered
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False)
    concept_tag: Mapped[str] = mapped_column(String, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interval_days: Mapped[float] = mapped_column(Float, nullable=False)
    ease: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)


class Streak(Base):
    __tablename__ = "streaks"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    current_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Quiz(Base):
    """Not in docs/SCHEMA.md — that doc predates the quiz feature. A quiz is
    scoped to one book and a subset of its chapters; its questions are a mix
    of reused lesson questions and freshly generated ones (see
    app/quizzes.py), referenced through QuizQuestion rather than duplicated."""

    __tablename__ = "quizzes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), nullable=False)
    chapter_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    difficulty: Mapped[str] = mapped_column(String, nullable=False, default="mixed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    # explicit foreign_keys: books.final_quiz_id also points at quizzes.id, so
    # there are two FK paths between these tables and SQLAlchemy can't infer
    # which one this relationship means without help.
    book: Mapped["Book"] = relationship(foreign_keys=[book_id])
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan", order_by="QuizQuestion.order"
    )


class QuizQuestion(Base):
    """Join row rather than a copy of Question — a book-sourced question
    stays the single source of truth (one row, answerable the same way
    whether reached from its lesson or from a quiz) and a freshly generated
    one is just a Question with lesson_id null (see Question.lesson_id)."""

    __tablename__ = "quiz_questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    quiz_id: Mapped[str] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    quiz: Mapped["Quiz"] = relationship(back_populates="quiz_questions")
    question: Mapped["Question"] = relationship()


class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id"), nullable=False)
    selected_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.created_at",
    )


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    conversation: Mapped["AIConversation"] = relationship(back_populates="messages")
