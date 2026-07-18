from datetime import datetime
from uuid import UUID
from typing import Optional, List, Any
from pydantic import BaseModel

# --- Course ---
class CourseBase(BaseModel):
    title: str
    slug: str
    description: Optional[str] = None
    short_desc: Optional[str] = None
    thumbnail: Optional[str] = None
    level: Optional[str] = None
    category: Optional[str] = None
    teacher_id: Optional[UUID] = None
    status: Optional[str] = None
    is_active: bool = True
    is_featured: bool = False

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    short_desc: Optional[str] = None
    thumbnail: Optional[str] = None
    level: Optional[str] = None
    category: Optional[str] = None
    teacher_id: Optional[UUID] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None

class CourseResponse(CourseBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    first_chapter_id: Optional[UUID] = None
    first_lesson_id: Optional[UUID] = None

    class Config:
        from_attributes = True

# --- Chapter ---
class ChapterBase(BaseModel):
    title: str
    description: Optional[str] = None
    sort_order: int = 0

class ChapterCreate(ChapterBase):
    course_id: Optional[UUID] = None

class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None

class ChapterResponse(ChapterBase):
    id: UUID
    course_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

# --- Lesson ---
class LessonBase(BaseModel):
    title: str
    content_type: str = "rich_text" # 'rich_text', 'quiz'
    sort_order: int = 0
    duration_min: int = 0
    is_free: bool = False
    quiz_id: Optional[UUID] = None

class LessonCreate(LessonBase):
    chapter_id: Optional[UUID] = None

class LessonUpdate(BaseModel):
    title: Optional[str] = None
    content_type: Optional[str] = None
    sort_order: Optional[int] = None
    duration_min: Optional[int] = None
    is_free: Optional[bool] = None
    quiz_id: Optional[UUID] = None
    chapter_id: Optional[UUID] = None

class LessonResponse(LessonBase):
    id: UUID
    chapter_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Lesson Content ---
class LessonContentBase(BaseModel):
    body: Any = None # JSONB (BlockNote) — legacy
    body_md: Optional[str] = None # Markdown content
    plain_text: Optional[str] = None
    version: int = 1

class LessonContentUpdate(BaseModel):
    body: Optional[Any] = None
    body_md: Optional[str] = None
    plain_text: Optional[str] = None
    version: Optional[int] = None

class LessonContentResponse(LessonContentBase):
    id: UUID
    lesson_id: UUID
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Composite / Extended ---
class ChapterWithLessons(ChapterResponse):
    lessons: List[LessonResponse] = []

class CourseWithChapters(CourseResponse):
    chapters: List[ChapterWithLessons] = []

class LessonReorderItem(BaseModel):
    id: UUID
    sort_order: int

class LessonReorder(BaseModel):
    lessons: List[LessonReorderItem]

class CourseListResponse(BaseModel):
    data: List[CourseResponse]
    total: int
    page: int
    size: int
