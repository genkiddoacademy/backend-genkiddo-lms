from datetime import date, datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, conint, validator

from app.api.v1.endpoints.auth import get_current_user, require_role
from app.core.postgre import supabase

router = APIRouter(tags=["Discovery Assessments"])
admin_required = require_role("admin")

AssessmentStatus = Literal["draft", "published"]
AttendanceStatus = Literal["present", "excused", "absent"]
SkillScore = conint(ge=1, le=5)


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class DiscoveryAssessmentCreate(BaseModel):
    student_id: Optional[str] = None
    program_name: Optional[str] = None
    course_name: Optional[str] = None
    session_number: int = Field(..., ge=1)
    session_title: str = Field(..., min_length=1)
    session_date: date
    mentor_name: Optional[str] = None
    attendance_status: AttendanceStatus = "present"
    learning_summary: str = Field(..., min_length=1)
    activities: str = Field(..., min_length=1)
    project_result: Optional[str] = None
    material_score: SkillScore
    logic_score: SkillScore
    practice_score: SkillScore
    creativity_score: SkillScore
    focus_score: SkillScore
    digital_ethics_score: Optional[SkillScore] = None
    communication_score: Optional[SkillScore] = None
    strengths: str = Field(..., min_length=1)
    improvements: str = Field(..., min_length=1)
    parent_recommendation: str = Field(..., min_length=1)
    next_session_plan: Optional[str] = None
    status: AssessmentStatus = "draft"

    _clean_program_name = validator("program_name", allow_reuse=True, pre=True)(_clean_text)
    _clean_course_name = validator("course_name", allow_reuse=True, pre=True)(_clean_text)
    _clean_mentor_name = validator("mentor_name", allow_reuse=True, pre=True)(_clean_text)
    _clean_project_result = validator("project_result", allow_reuse=True, pre=True)(_clean_text)
    _clean_next_session_plan = validator("next_session_plan", allow_reuse=True, pre=True)(_clean_text)


class DiscoveryAssessmentUpdate(BaseModel):
    student_id: Optional[str] = None
    program_name: Optional[str] = None
    course_name: Optional[str] = None
    session_number: Optional[int] = Field(None, ge=1)
    session_title: Optional[str] = None
    session_date: Optional[date] = None
    mentor_name: Optional[str] = None
    attendance_status: Optional[AttendanceStatus] = None
    learning_summary: Optional[str] = None
    activities: Optional[str] = None
    project_result: Optional[str] = None
    material_score: Optional[SkillScore] = None
    logic_score: Optional[SkillScore] = None
    practice_score: Optional[SkillScore] = None
    creativity_score: Optional[SkillScore] = None
    focus_score: Optional[SkillScore] = None
    digital_ethics_score: Optional[SkillScore] = None
    communication_score: Optional[SkillScore] = None
    strengths: Optional[str] = None
    improvements: Optional[str] = None
    parent_recommendation: Optional[str] = None
    next_session_plan: Optional[str] = None
    status: Optional[AssessmentStatus] = None

    _clean_program_name = validator("program_name", allow_reuse=True, pre=True)(_clean_text)
    _clean_course_name = validator("course_name", allow_reuse=True, pre=True)(_clean_text)
    _clean_mentor_name = validator("mentor_name", allow_reuse=True, pre=True)(_clean_text)
    _clean_project_result = validator("project_result", allow_reuse=True, pre=True)(_clean_text)
    _clean_next_session_plan = validator("next_session_plan", allow_reuse=True, pre=True)(_clean_text)


def _get_student(student_id: Optional[str]) -> Optional[dict]:
    if not student_id:
        return None
    student_res = supabase.table("students").select("*").eq("id", student_id).execute()
    return student_res.data[0] if student_res.data else None


def _build_student_map(student_ids: list[str]) -> dict[str, dict]:
    if not student_ids:
        return {}
    student_res = supabase.table("students").select("*").in_("id", list(set(student_ids))).execute()
    return {row["id"]: row for row in (student_res.data or [])}


def _build_parent_map(parent_ids: list[str]) -> dict[str, dict]:
    if not parent_ids:
        return {}
    parent_res = supabase.table("parents").select("*").in_("id", list(set(parent_ids))).execute()
    return {row["id"]: row for row in (parent_res.data or [])}


def _enrich_assessment_rows(rows: list[dict]) -> list[dict]:
    student_map = _build_student_map([row.get("student_id") for row in rows if row.get("student_id")])
    parent_map = _build_parent_map([row.get("parent_id") for row in rows if row.get("parent_id")])
    enriched: list[dict] = []

    for row in rows:
        item = dict(row)
        student = student_map.get(item.get("student_id"))
        parent = parent_map.get(item.get("parent_id"))
        item["student_name"] = student.get("name") if student else None
        item["parent_name"] = parent.get("name") if parent else None
        enriched.append(item)

    return enriched


def _assessment_or_404(assessment_id: str) -> dict:
    res = supabase.table("discovery_assessments").select("*").eq("id", assessment_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Assessment tidak ditemukan")
    return res.data[0]


def _build_payload(body: DiscoveryAssessmentCreate | DiscoveryAssessmentUpdate) -> dict:
    data = body.dict(exclude_unset=True)
    if "session_date" in data and isinstance(data["session_date"], date):
        data["session_date"] = data["session_date"].isoformat()
    return data


def _attach_student_parent(payload: dict) -> dict:
    student_id = payload.get("student_id")
    if not student_id:
        payload["parent_id"] = None
        return payload

    student = _get_student(student_id)
    if not student:
        raise HTTPException(status_code=400, detail="Student tidak ditemukan")

    payload["parent_id"] = student.get("parent_id")
    return payload


def _get_mentor_profile(current_user: dict) -> dict:
    if current_user.get("role") != "mentor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses ditolak")

    mentor_res = supabase.table("mentors").select("id,parent_id,is_active").eq("parent_id", current_user["id"]).execute()
    if not mentor_res.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses mentor tidak ditemukan")

    mentor = mentor_res.data[0]
    if mentor.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akun Anda telah dinonaktifkan oleh Admin.")
    return mentor


def _get_mentor_student_ids(mentor_profile_id: str) -> list[str]:
    schedules_res = supabase.table("schedules").select("enrollment_id").eq("mentor_id", mentor_profile_id).execute()
    enrollment_ids = [row.get("enrollment_id") for row in (schedules_res.data or []) if row.get("enrollment_id")]
    if not enrollment_ids:
        return []

    enrollments_res = supabase.table("enrollments").select("student_id").in_("id", enrollment_ids).execute()
    return [row.get("student_id") for row in (enrollments_res.data or []) if row.get("student_id")]


@router.get("/discovery-assessments")
async def list_discovery_assessments(current_user: dict = Depends(admin_required)):
    res = (
        supabase.table("discovery_assessments")
        .select("*")
        .order("session_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    data = _enrich_assessment_rows(res.data or [])
    return {"data": data, "total": len(data)}


@router.get("/discovery-assessments/{assessment_id}")
async def get_discovery_assessment(assessment_id: str, current_user: dict = Depends(admin_required)):
    item = _assessment_or_404(assessment_id)
    return _enrich_assessment_rows([item])[0]


@router.post("/discovery-assessments", status_code=201)
async def create_discovery_assessment(
    body: DiscoveryAssessmentCreate,
    current_user: dict = Depends(admin_required),
):
    payload = _attach_student_parent(_build_payload(body))
    now = datetime.utcnow().isoformat()
    payload["created_at"] = now
    payload["updated_at"] = now
    res = supabase.table("discovery_assessments").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat assessment")
    return _enrich_assessment_rows([res.data[0]])[0]


@router.put("/discovery-assessments/{assessment_id}")
async def update_discovery_assessment(
    assessment_id: str,
    body: DiscoveryAssessmentUpdate,
    current_user: dict = Depends(admin_required),
):
    _assessment_or_404(assessment_id)
    payload = _build_payload(body)
    payload = _attach_student_parent(payload) if "student_id" in payload else payload
    payload["updated_at"] = datetime.utcnow().isoformat()
    res = supabase.table("discovery_assessments").update(payload).eq("id", assessment_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui assessment")
    return _enrich_assessment_rows([res.data[0]])[0]


@router.delete("/discovery-assessments/{assessment_id}")
async def delete_discovery_assessment(assessment_id: str, current_user: dict = Depends(admin_required)):
    _assessment_or_404(assessment_id)
    res = supabase.table("discovery_assessments").delete().eq("id", assessment_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menghapus assessment")
    return {"message": "Assessment berhasil dihapus"}


@router.patch("/discovery-assessments/{assessment_id}/publish")
async def publish_discovery_assessment(assessment_id: str, current_user: dict = Depends(admin_required)):
    _assessment_or_404(assessment_id)
    res = (
        supabase.table("discovery_assessments")
        .update({"status": "published", "updated_at": datetime.utcnow().isoformat()})
        .eq("id", assessment_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal publish assessment")
    return _enrich_assessment_rows([res.data[0]])[0]


@router.get("/mentor/discovery-assessments")
async def list_mentor_discovery_assessments(current_user: dict = Depends(get_current_user)):
    _get_mentor_profile(current_user)
    student_res = supabase.table("students").select("id").execute()
    student_ids = [row["id"] for row in (student_res.data or [])]
    if not student_ids:
        return {"data": [], "total": 0}

    res = (
        supabase.table("discovery_assessments")
        .select("*")
        .in_("student_id", student_ids)
        .order("session_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    data = _enrich_assessment_rows(res.data or [])
    return {"data": data, "total": len(data)}


@router.post("/mentor/discovery-assessments", status_code=201)
async def create_mentor_discovery_assessment(
    body: DiscoveryAssessmentCreate,
    current_user: dict = Depends(get_current_user),
):
    _get_mentor_profile(current_user)
    student_id = body.student_id
    if not student_id:
        raise HTTPException(status_code=400, detail="Student wajib dipilih")

    student = _get_student(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student tidak ditemukan")

    payload = _attach_student_parent(_build_payload(body))
    payload["mentor_name"] = current_user.get("name") or body.mentor_name or "Mentor"
    now = datetime.utcnow().isoformat()
    payload["created_at"] = now
    payload["updated_at"] = now
    res = supabase.table("discovery_assessments").insert(payload).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat assessment")
    return _enrich_assessment_rows([res.data[0]])[0]


@router.get("/parent/discovery-assessments")
async def list_parent_discovery_assessments(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "parent":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses ditolak")

    student_res = supabase.table("students").select("*").eq("parent_id", current_user["id"]).execute()
    student_ids = [row["id"] for row in (student_res.data or [])]
    if not student_ids:
        return {"data": [], "total": 0}

    res = (
        supabase.table("discovery_assessments")
        .select("*")
        .in_("student_id", student_ids)
        .eq("status", "published")
        .order("session_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    data = _enrich_assessment_rows(res.data or [])
    return {"data": data, "total": len(data)}


@router.get("/parent/discovery-assessments/{assessment_id}")
async def get_parent_discovery_assessment(assessment_id: str, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "parent":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses ditolak")

    item = _assessment_or_404(assessment_id)
    if item.get("status") != "published":
        raise HTTPException(status_code=404, detail="Assessment tidak ditemukan")

    student = _get_student(item.get("student_id"))
    if not student or student.get("parent_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Assessment tidak ditemukan")

    return _enrich_assessment_rows([item])[0]
