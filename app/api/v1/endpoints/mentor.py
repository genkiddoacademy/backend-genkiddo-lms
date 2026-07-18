from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from uuid import uuid4
import os
from app.api.v1.endpoints.auth import get_current_user
from app.core.postgre import supabase
from app.core.config import settings

router = APIRouter(prefix="/api/v1/mentor", tags=["Mentor"])

class AttendanceRequest(BaseModel):
    student_id: UUID
    status: str  # present, absent, permission, late
    notes: Optional[str] = None

class SessionReportRequest(BaseModel):
    student_id: UUID
    material_summary: str
    understanding_score: int
    logic_score: int
    creativity_score: int
    independence_score: int
    digital_ethics_score: int
    mentor_notes: str
    recommendation: Optional[str] = None
    status: str = "draft"  # draft, submitted

class MentorMaterialCreate(BaseModel):
    title: str
    description: Optional[str] = None
    course_id: Optional[UUID] = None
    file_url: str

class AssignmentCreate(BaseModel):
    batch_id: UUID
    course_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    assignment_type: str = "task"
    due_at: Optional[str] = None
    attachment_url: Optional[str] = None
    status: str = "published"

# Helper: Get Mentor ID
def get_mentor_id(current_user: dict) -> UUID:
    if current_user.get("role") != "mentor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses ditolak: role mentor diperlukan"
        )
    user_id = current_user["id"]
    mentor_res = supabase.table("mentors").select("id").eq("parent_id", user_id).execute()
    if not mentor_res.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses ditolak: Anda bukan seorang mentor"
        )
    return mentor_res.data[0]["id"]

def _clean_upload_name(filename: str) -> str:
    base = filename or "attachment"
    clean = "".join([c if c.isalnum() or c in (".", "-", "_") else "_" for c in base])
    return f"{uuid4().hex}_{clean}"

@router.get("/schedules")
async def get_mentor_schedules(current_user: dict = Depends(get_current_user)):
    mentor_id = get_mentor_id(current_user)
    
    schedules_res = supabase.table("schedules")\
        .select("*")\
        .eq("mentor_id", str(mentor_id))\
        .order("start_time")\
        .execute()
    
    schedules = schedules_res.data or []
    result = []
    
    for s in schedules:
        course_title = "Materi Belajar"
        if s.get("course_id"):
            c_res = supabase.table("courses").select("title").eq("id", s["course_id"]).execute()
            if c_res.data:
                course_title = c_res.data[0]["title"]
                
        student_name = "Siswa"
        student_id = None
        if s.get("enrollment_id"):
            e_res = supabase.table("enrollments").select("student_id").eq("id", s["enrollment_id"]).execute()
            if e_res.data:
                student_id = e_res.data[0]["student_id"]
                st_res = supabase.table("students").select("name").eq("id", student_id).execute()
                if st_res.data:
                    student_name = st_res.data[0]["name"]
                    
        result.append({
            "id": s["id"],
            "title": s["title"],
            "class_type": s["class_type"],
            "start_time": s["start_time"],
            "end_time": s["end_time"],
            "location": s.get("location"),
            "zoom_meeting_id": s.get("zoom_meeting_id"),
            "zoom_join_url": s.get("zoom_join_url"),
            "zoom_start_url": s.get("zoom_start_url"),
            "status": s["status"],
            "course_id": s.get("course_id"),
            "course_title": course_title,
            "student_id": student_id,
            "student_name": student_name
        })
        
    return result

@router.get("/courses")
async def list_mentor_courses(current_user: dict = Depends(get_current_user)):
    get_mentor_id(current_user)
    res = supabase.table("courses").select("*").execute()
    return {"data": res.data or []}

@router.get("/batches")
async def list_mentor_batches(current_user: dict = Depends(get_current_user)):
    get_mentor_id(current_user)
    res = supabase.table("classes").select("*").execute()
    return {"data": res.data or []}


@router.get("/assessment-students")
async def get_mentor_assessment_students(current_user: dict = Depends(get_current_user)):
    get_mentor_id(current_user)
    res = supabase.table("students").select("id,name,username,created_at").order("created_at", desc=True).execute()
    students = []
    for student in (res.data or []):
        students.append({
            "id": student["id"],
            "name": student.get("name"),
            "username": student.get("username"),
            "courses": [],
        })
    return {"data": students}


@router.get("/students")
async def get_mentor_students(current_user: dict = Depends(get_current_user)):
    mentor_id = get_mentor_id(current_user)
    schedules_res = supabase.table("schedules").select("*").eq("mentor_id", str(mentor_id)).execute()
    students_by_id = {}

    for schedule in (schedules_res.data or []):
        student_id = None
        course_title = "Course"
        enrollment_id = None
        if schedule.get("course_id"):
            course_res = supabase.table("courses").select("*").eq("id", schedule["course_id"]).execute()
            if course_res.data:
                course_title = course_res.data[0].get("title") or course_title
        if schedule.get("enrollment_id"):
            enrollment_res = supabase.table("enrollments").select("*").eq("id", schedule["enrollment_id"]).execute()
            if enrollment_res.data:
                student_id = enrollment_res.data[0].get("student_id")
                enrollment_id = enrollment_res.data[0].get("id")
        if not student_id:
            continue

        if student_id not in students_by_id:
            student_res = supabase.table("students").select("*").eq("id", student_id).execute()
            if not student_res.data:
                continue
            student = student_res.data[0]
            students_by_id[student_id] = {
                "id": student["id"],
                "name": student.get("name"),
                "username": student.get("username"),
                "age": student.get("age"),
                "gender": student.get("gender"),
                "coding_experience": student.get("coding_experience"),
                "school_origin": student.get("school_origin"),
                "courses": [],
                "schedule_count": 0,
                "attendance_logs": [],
                "session_reports": [],
            }

        # Avoid duplicates in courses
        course_exists = False
        for c in students_by_id[student_id]["courses"]:
            if c["title"] == course_title:
                course_exists = True
                break
        if not course_exists:
            students_by_id[student_id]["courses"].append({
                "title": course_title,
                "enrollment_id": enrollment_id
            })
            
        students_by_id[student_id]["schedule_count"] += 1

        attendance_res = supabase.table("attendances").select("*").eq("schedule_id", schedule["id"]).eq("student_id", student_id).execute()
        students_by_id[student_id]["attendance_logs"].extend(attendance_res.data or [])
        report_res = supabase.table("session_reports").select("*").eq("schedule_id", schedule["id"]).eq("student_id", student_id).execute()
        students_by_id[student_id]["session_reports"].extend(report_res.data or [])

    result = []
    for student in students_by_id.values():
        logs = student["attendance_logs"]
        present_count = len([log for log in logs if log.get("status") == "present"])
        student["attendance_rate"] = round((present_count / len(logs)) * 100) if logs else 0
        result.append(student)

    return {"data": result}

@router.get("/schedules/{schedule_id}/details")
async def get_schedule_details(schedule_id: UUID, current_user: dict = Depends(get_current_user)):
    mentor_id = get_mentor_id(current_user)
    
    s_res = supabase.table("schedules").select("*").eq("id", str(schedule_id)).eq("mentor_id", str(mentor_id)).execute()
    if not s_res.data:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan atau Anda tidak mengajar jadwal ini")
    
    schedule = s_res.data[0]
    
    # Resolve student
    student_info = None
    student_id = None
    if schedule.get("enrollment_id"):
        e_res = supabase.table("enrollments").select("student_id").eq("id", schedule["enrollment_id"]).execute()
        if e_res.data:
            student_id = e_res.data[0]["student_id"]
            st_res = supabase.table("students").select("*").eq("id", student_id).execute()
            if st_res.data:
                student_info = st_res.data[0]
                
    # Get attendance
    attendance = None
    if student_id:
        att_res = supabase.table("attendances")\
            .select("*")\
            .eq("schedule_id", str(schedule_id))\
            .eq("student_id", str(student_id))\
            .execute()
        if att_res.data:
            attendance = att_res.data[0]
            
    # Get session report
    session_report = None
    if student_id:
        rep_res = supabase.table("session_reports")\
            .select("*")\
            .eq("schedule_id", str(schedule_id))\
            .eq("student_id", str(student_id))\
            .execute()
        if rep_res.data:
            session_report = rep_res.data[0]
            
    return {
        "schedule": schedule,
        "student": student_info,
        "attendance": attendance,
        "session_report": session_report
    }

@router.post("/schedules/{schedule_id}/attendance")
async def submit_attendance(
    schedule_id: UUID,
    req: AttendanceRequest,
    current_user: dict = Depends(get_current_user)
):
    mentor_id = get_mentor_id(current_user)
    
    # Verify schedule belongs to mentor
    s_res = supabase.table("schedules").select("id").eq("id", str(schedule_id)).eq("mentor_id", str(mentor_id)).execute()
    if not s_res.data:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
    payload = {
        "schedule_id": str(schedule_id),
        "student_id": str(req.student_id),
        "status": req.status,
        "notes": req.notes
    }
    
    # Upsert attendance record
    res = supabase.table("attendances").upsert(payload, on_conflict="schedule_id, student_id").execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menyimpan absensi")
        
    return {"message": "Absensi berhasil disimpan", "data": res.data[0]}

@router.post("/schedules/{schedule_id}/session-report")
async def submit_session_report(
    schedule_id: UUID,
    req: SessionReportRequest,
    current_user: dict = Depends(get_current_user)
):
    mentor_id = get_mentor_id(current_user)
    
    # Verify schedule belongs to mentor
    s_res = supabase.table("schedules").select("id").eq("id", str(schedule_id)).eq("mentor_id", str(mentor_id)).execute()
    if not s_res.data:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
    payload = {
        "schedule_id": str(schedule_id),
        "student_id": str(req.student_id),
        "mentor_id": str(mentor_id),
        "material_summary": req.material_summary,
        "understanding_score": req.understanding_score,
        "logic_score": req.logic_score,
        "creativity_score": req.creativity_score,
        "independence_score": req.independence_score,
        "digital_ethics_score": req.digital_ethics_score,
        "mentor_notes": req.mentor_notes,
        "recommendation": req.recommendation,
        "status": req.status
    }
    
    res = supabase.table("session_reports").upsert(payload, on_conflict="schedule_id, student_id").execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menyimpan laporan sesi")
        
    return {"message": "Laporan sesi berhasil disimpan", "data": res.data[0]}

# Resource upload specifically for mentors
@router.post("/upload-resource")
async def upload_mentor_resource(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    import uuid
    from app.services.storage import storage_client

    content = await file.read()
    filename = f"{uuid4().hex}_{file.filename or 'attachment'}"
    r2_path = f"materials/attachments/{filename}"
    
    storage_client.upload_file(r2_path, content, file.content_type)
        
    return {"url": f"/uploads/{r2_path}"}

@router.get("/materials")
async def list_mentor_materials(current_user: dict = Depends(get_current_user)):
    mentor_id = get_mentor_id(current_user)
    res = supabase.table("mentor_materials").select("*").eq("mentor_id", str(mentor_id)).order("created_at", desc=True).execute()
    materials = res.data or []
    for material in materials:
        material["course_title"] = None
        if material.get("course_id"):
            course_res = supabase.table("courses").select("*").eq("id", material["course_id"]).execute()
            if course_res.data:
                material["course_title"] = course_res.data[0].get("title")
    return {"data": materials}

@router.post("/materials", status_code=201)
async def create_mentor_material(body: MentorMaterialCreate, current_user: dict = Depends(get_current_user)):
    mentor_id = get_mentor_id(current_user)
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Judul materi wajib diisi")
    if not body.file_url.startswith("/uploads/materials/attachments/"):
        raise HTTPException(status_code=400, detail="File materi harus berada di /uploads/materials/attachments/")

    data = {
        "mentor_id": str(mentor_id),
        "title": body.title.strip(),
        "description": body.description or "",
        "course_id": str(body.course_id) if body.course_id else None,
        "file_url": body.file_url,
    }
    res = supabase.table("mentor_materials").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menyimpan materi")
    return res.data[0]

@router.delete("/materials/{material_id}")
async def delete_mentor_material(material_id: UUID, current_user: dict = Depends(get_current_user)):
    mentor_id = get_mentor_id(current_user)
    existing = supabase.table("mentor_materials").select("id").eq("id", str(material_id)).eq("mentor_id", str(mentor_id)).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Materi tidak ditemukan")
    supabase.table("mentor_materials").delete().eq("id", str(material_id)).execute()
    return {"message": "Materi berhasil dihapus"}

@router.get("/assignments")
async def list_mentor_assignments(current_user: dict = Depends(get_current_user)):
    mentor_id = get_mentor_id(current_user)
    res = supabase.table("assignments").select("*").eq("mentor_id", str(mentor_id)).order("created_at", desc=True).execute()
    assignments = res.data or []
    for assignment in assignments:
        assignment["batch_name"] = None
        if assignment.get("batch_id"):
            batch_res = supabase.table("classes").select("*").eq("id", assignment["batch_id"]).execute()
            if batch_res.data:
                assignment["batch_name"] = batch_res.data[0].get("display_name") or batch_res.data[0].get("name")
    return {"data": assignments}

@router.post("/assignments", status_code=201)
async def create_mentor_assignment(body: AssignmentCreate, current_user: dict = Depends(get_current_user)):
    mentor_id = get_mentor_id(current_user)
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Judul tugas wajib diisi")
    if body.assignment_type not in ("task", "quiz"):
        raise HTTPException(status_code=400, detail="Jenis assignment tidak valid")

    batch_res = supabase.table("classes").select("id").eq("id", str(body.batch_id)).execute()
    if not batch_res.data:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")

    data = {
        "batch_id": str(body.batch_id),
        "course_id": str(body.course_id) if body.course_id else None,
        "mentor_id": str(mentor_id),
        "title": body.title.strip(),
        "description": body.description or "",
        "assignment_type": body.assignment_type,
        "due_at": body.due_at,
        "attachment_url": body.attachment_url,
        "status": body.status,
    }
    res = supabase.table("assignments").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat assignment")
    return res.data[0]


class ZoomLinkRequest(BaseModel):
    zoom_join_url: str

@router.post("/schedules/{schedule_id}/zoom-link")
async def update_zoom_link(
    schedule_id: UUID,
    req: ZoomLinkRequest,
    current_user: dict = Depends(get_current_user)
):
    mentor_id = get_mentor_id(current_user)
    
    # Verify schedule belongs to mentor
    s_res = supabase.table("schedules").select("id").eq("id", str(schedule_id)).eq("mentor_id", str(mentor_id)).execute()
    if not s_res.data:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
        
    res = supabase.table("schedules").update({"zoom_join_url": req.zoom_join_url}).eq("id", str(schedule_id)).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui link Zoom")
        
    return {"message": "Link Zoom berhasil diperbarui", "data": res.data[0]}

# --- Mentor Grading & Submissions ---

class GradeSubmissionRequest(BaseModel):
    grade: float
    feedback: Optional[str] = None

@router.get("/assignments/{assignment_id}/submissions")
async def list_assignment_submissions(
    assignment_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    mentor_id = get_mentor_id(current_user)
    
    # Verify assignment belongs to this mentor
    assign_res = supabase.table("assignments").select("*").eq("id", str(assignment_id)).eq("mentor_id", str(mentor_id)).execute()
    if not assign_res.data:
        raise HTTPException(status_code=404, detail="Assignment tidak ditemukan atau Anda tidak mengajar kelas ini")
        
    # Fetch all submissions for this assignment
    sub_res = supabase.table("assignment_submissions").select("*").eq("assignment_id", str(assignment_id)).execute()
    submissions = sub_res.data or []
    
    result = []
    for s in submissions:
        # Fetch student name
        st_res = supabase.table("students").select("name").eq("id", s["student_id"]).execute()
        student_name = st_res.data[0]["name"] if st_res.data else "Siswa"
        
        result.append({
            "id": s["id"],
            "student_id": s["student_id"],
            "student_name": student_name,
            "submission_url": s["submission_url"],
            "notes": s.get("notes"),
            "grade": s.get("grade"),
            "feedback": s.get("feedback"),
            "submitted_at": s.get("submitted_at"),
            "graded_at": s.get("graded_at")
        })
        
    return {"data": result}

@router.post("/submissions/{submission_id}/grade")
async def grade_submission(
    submission_id: UUID,
    body: GradeSubmissionRequest,
    current_user: dict = Depends(get_current_user)
):
    mentor_id = get_mentor_id(current_user)
    
    # Get submission to verify assignment ownership
    sub_res = supabase.table("assignment_submissions").select("assignment_id").eq("id", str(submission_id)).execute()
    if not sub_res.data:
        raise HTTPException(status_code=404, detail="Pengumpulan tugas tidak ditemukan")
        
    assignment_id = sub_res.data[0]["assignment_id"]
    
    # Verify assignment belongs to this mentor
    assign_res = supabase.table("assignments").select("id").eq("id", assignment_id).eq("mentor_id", str(mentor_id)).execute()
    if not assign_res.data:
        raise HTTPException(status_code=403, detail="Akses ditolak: Anda tidak memiliki wewenang menilai tugas ini")
        
    # Update submission with grade, feedback, graded_by, and graded_at
    from datetime import datetime
    payload = {
        "grade": body.grade,
        "feedback": body.feedback,
        "graded_by": current_user["id"],  # parent_id is the user id for the mentor
        "graded_at": datetime.now().isoformat()
    }
    
    up_res = supabase.table("assignment_submissions").update(payload).eq("id", str(submission_id)).execute()
    if not up_res.data:
        raise HTTPException(status_code=500, detail="Gagal menyimpan penilaian")
        
    return {"message": "Penilaian berhasil disimpan", "data": up_res.data[0]}


class FinalReportRequest(BaseModel):
    title: str
    summary: str
    strengths: str
    improvements: str
    recommendation: str
    status: str = "draft"  # draft, submitted

@router.get("/enrollments/{enrollment_id}/final-report")
async def get_final_report(
    enrollment_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    mentor_id = get_mentor_id(current_user)
    
    # Verify enrollment exists
    enroll_res = supabase.table("enrollments").select("*").eq("id", str(enrollment_id)).execute()
    if not enroll_res.data:
        raise HTTPException(status_code=404, detail="Enrollment tidak ditemukan")
    enrollment = enroll_res.data[0]
    
    # Verify mentor teaches this student in a schedule
    s_res = supabase.table("schedules").select("id").eq("enrollment_id", str(enrollment_id)).eq("mentor_id", str(mentor_id)).execute()
    if not s_res.data:
        raise HTTPException(status_code=403, detail="Akses ditolak: Anda tidak mengajar siswa di kelas ini")
        
    report_res = supabase.table("final_reports").select("*").eq("enrollment_id", str(enrollment_id)).execute()
    report = report_res.data[0] if report_res.data else None
    
    return {"data": report}

@router.post("/enrollments/{enrollment_id}/final-report")
async def submit_final_report(
    enrollment_id: UUID,
    req: FinalReportRequest,
    current_user: dict = Depends(get_current_user)
):
    mentor_id = get_mentor_id(current_user)
    
    # Verify enrollment exists
    enroll_res = supabase.table("enrollments").select("*").eq("id", str(enrollment_id)).execute()
    if not enroll_res.data:
        raise HTTPException(status_code=404, detail="Enrollment tidak ditemukan")
    enrollment = enroll_res.data[0]
    
    # Verify mentor teaches this student in a schedule
    s_res = supabase.table("schedules").select("id").eq("enrollment_id", str(enrollment_id)).eq("mentor_id", str(mentor_id)).execute()
    if not s_res.data:
        raise HTTPException(status_code=403, detail="Akses ditolak: Anda tidak mengajar siswa di kelas ini")
        
    if req.status not in ("draft", "submitted"):
        raise HTTPException(status_code=400, detail="Status harus berupa 'draft' atau 'submitted'")
        
    payload = {
        "enrollment_id": str(enrollment_id),
        "student_id": enrollment["student_id"],
        "mentor_id": str(mentor_id),
        "title": req.title,
        "summary": req.summary,
        "strengths": req.strengths,
        "improvements": req.improvements,
        "recommendation": req.recommendation,
        "status": req.status
    }
    
    # Check if final report already exists
    existing = supabase.table("final_reports").select("id").eq("enrollment_id", str(enrollment_id)).execute()
    if existing.data:
        # Update
        res = supabase.table("final_reports").update(payload).eq("enrollment_id", str(enrollment_id)).execute()
    else:
        # Insert
        res = supabase.table("final_reports").insert(payload).execute()
        
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menyimpan laporan akhir")
        
    return {"message": "Laporan akhir berhasil disimpan", "data": res.data[0]}

