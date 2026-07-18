from datetime import datetime
from uuid import UUID
from typing import Optional, List, Any
from pydantic import BaseModel

# --- Quiz ---
class QuizBase(BaseModel):
    title: str
    lesson_id: Optional[UUID] = None
    max_attempts: Optional[int] = None
    duration: Optional[int] = None # in minutes
    passing_percentage: float = 0
    total_marks: float = 0
    shuffle_questions: bool = False
    limit_questions_to: Optional[int] = None
    enable_negative_marking: bool = False
    marks_to_cut: float = 0
    show_answers: bool = False
    show_submission_history: bool = False

class QuizCreate(QuizBase):
    pass

class QuizUpdate(BaseModel):
    title: Optional[str] = None
    lesson_id: Optional[UUID] = None
    max_attempts: Optional[int] = None
    duration: Optional[int] = None
    passing_percentage: Optional[float] = None
    total_marks: Optional[float] = None
    shuffle_questions: Optional[bool] = None
    limit_questions_to: Optional[int] = None
    enable_negative_marking: Optional[bool] = None
    marks_to_cut: Optional[float] = None
    show_answers: Optional[bool] = None
    show_submission_history: Optional[bool] = None

class QuizResponse(QuizBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Question ---
class QuestionBase(BaseModel):
    question: Any # JSON (BlockNote)
    type: str = "Choices" # 'Choices', 'User Input', 'Open Ended'
    marks: float = 1
    sort_order: int = 0
    multiple: bool = False
    option_1: Optional[str] = None
    option_2: Optional[str] = None
    option_3: Optional[str] = None
    option_4: Optional[str] = None
    is_correct_1: bool = False
    is_correct_2: bool = False
    is_correct_3: bool = False
    is_correct_4: bool = False
    explanation_1: Optional[str] = None
    explanation_2: Optional[str] = None
    explanation_3: Optional[str] = None
    explanation_4: Optional[str] = None
    possibility_1: Optional[str] = None
    possibility_2: Optional[str] = None
    possibility_3: Optional[str] = None
    possibility_4: Optional[str] = None

class QuestionCreate(QuestionBase):
    quiz_id: UUID

class QuestionUpdate(BaseModel):
    question: Optional[Any] = None
    type: Optional[str] = None
    marks: Optional[float] = None
    sort_order: Optional[int] = None
    multiple: Optional[bool] = None
    option_1: Optional[str] = None
    option_2: Optional[str] = None
    option_3: Optional[str] = None
    option_4: Optional[str] = None
    is_correct_1: Optional[bool] = None
    is_correct_2: Optional[bool] = None
    is_correct_3: Optional[bool] = None
    is_correct_4: Optional[bool] = None
    explanation_1: Optional[str] = None
    explanation_2: Optional[str] = None
    explanation_3: Optional[str] = None
    explanation_4: Optional[str] = None
    possibility_1: Optional[str] = None
    possibility_2: Optional[str] = None
    possibility_3: Optional[str] = None
    possibility_4: Optional[str] = None

class QuestionResponse(QuestionBase):
    id: UUID
    quiz_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

# --- Quiz Submission ---
class QuizSubmissionBase(BaseModel):
    quiz_id: UUID
    student_id: UUID
    score: float = 0
    score_out_of: float = 0
    percentage: float = 0
    is_open_ended: bool = False
    result: List[Any] = [] # [{question_id, answer, is_correct, marks_earned}]
    attempt_number: int = 1

class QuizSubmissionCreate(QuizSubmissionBase):
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None

class QuizSubmissionResponse(QuizSubmissionBase):
    id: UUID
    started_at: datetime
    submitted_at: datetime

    class Config:
        from_attributes = True

# --- Interaction Schemas ---
class QuizAnswer(BaseModel):
    question_id: UUID
    answer: Any

class QuizSubmitRequest(BaseModel):
    quiz_id: UUID
    answers: List[QuizAnswer]

class QuizSubmitResponse(BaseModel):
    score: float
    percentage: float
    is_passed: bool
    result: List[Any]

class QuizWithQuestions(QuizResponse):
    questions: List[QuestionResponse] = []
