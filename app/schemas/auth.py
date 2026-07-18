from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    name: str
    whatsapp: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: "UserResponse"

class TokenData(BaseModel):
    email: Optional[str] = None

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    whatsapp_number: str
    password: str

class LoginRequest(BaseModel):
    email: str # Can be email or username
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    username: Optional[str] = None
    whatsapp_number: Optional[str] = None
    city: Optional[str] = None
    role: str = "parent"
    is_verified: Optional[bool] = None
    created_at: Optional[str] = None

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class DashboardStatsResponse(BaseModel):
    children: list["ChildDashboardData"]
    has_pending_registration: bool = False
    pending_registration_id: Optional[str] = None

class ChildDashboardData(BaseModel):
    id: str
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    courses: list["CourseStats"]
    current_classes: list["ClassInfo"]
    upcoming_meetings: list["MeetingInfo"]
    is_paid: bool = False
    school_origin: Optional[str] = None
    username: Optional[str] = None
    total_courses: int = 0
    completed_sessions: int = 0
    certificates_count: int = 0
    learning_points: int = 0

class CourseStats(BaseModel):
    course_title: str
    course_name: str
    progress: float = 0
    completed_chapters: int = 0
    completed_sessions: int = 0
    avg_quiz_score: float = 0
    scores: "ScoreBreakdown"

class ScoreBreakdown(BaseModel):
    pretest: Optional[float] = None
    posttest: Optional[float] = None
    quiz: Optional[float] = None
    final_project: Optional[float] = None

class ClassInfo(BaseModel):
    title: str
    materi: str
    siswa: str

class MeetingInfo(BaseModel):
    title: str
    date: str
