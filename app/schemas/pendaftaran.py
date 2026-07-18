from pydantic import BaseModel, EmailStr, UUID4
from typing import List, Optional

class ParentInfo(BaseModel):
    parent_email: EmailStr
    parent_name: str
    whatsapp_number: str
    city: str
    source: str

class StudentInfo(BaseModel):
    student_id: Optional[UUID4] = None
    student_name: str
    student_age: int
    student_gender: str
    coding_experience: str
    interests: List[str]
    school_origin: Optional[str] = None

class CourseInfo(BaseModel):
    class_id: UUID4
    expectation: str
    promo_code: Optional[str] = None

class RegistrationRequest(BaseModel):
    parent: ParentInfo
    student: StudentInfo
    course: CourseInfo

class RegistrationItem(BaseModel):
    student: StudentInfo
    course: CourseInfo

class BatchRegistrationRequest(BaseModel):
    parent: ParentInfo
    items: list[RegistrationItem]

class PromoValidateRequest(BaseModel):
    code: str
    class_id: UUID4
    parent_email: Optional[str] = None
    batch_count: int = 1