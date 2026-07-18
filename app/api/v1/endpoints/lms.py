from fastapi import APIRouter, HTTPException, Depends, Query, Header
from app.api.v1.endpoints.auth import get_current_user
from app.core.postgre import supabase
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

router = APIRouter(prefix="/lms", tags=["LMS Student endpoints"])

# --- Courses ---

@router.get("/courses")
async def get_published_courses(
    category: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = None
    student_status = None
    if current_user.get("role") == "student":
        resolved_student_id = current_user["id"]
        student_status = current_user.get("status")
    elif current_user.get("role") == "parent" and x_active_student_id:
        resolved_student_id = x_active_student_id
        student_res = supabase.table("students").select("status").eq("id", resolved_student_id).execute()
        student_status = student_res.data[0].get("status") if student_res.data else "preview"
        
    if student_status == "preview":
        return []

    if resolved_student_id:
        enroll_res = supabase.table("enrollments")\
            .select("course_id")\
            .eq("student_id", resolved_student_id)\
            .eq("status", "active")\
            .execute()
        enrolled_course_ids = [e["course_id"] for e in enroll_res.data] if enroll_res.data else []
        if not enrolled_course_ids:
            return []
        query = supabase.table("courses").select("*, chapters(*, lessons(*))").in_("id", enrolled_course_ids).eq("status", "published")
    else:
        query = supabase.table("courses").select("*, chapters(*, lessons(*))").eq("status", "published")

    if category:
        query = query.eq("category", category)
    if level:
        query = query.eq("level", level)
    
    res = query.execute()
    data = res.data or []
    
    if search:
        s = search.lower()
        data = [c for c in data if s in c.get("title", "").lower() or (c.get("description") and s in c.get("description", "").lower())]
    
    # Calculate progress per course from lesson_progress
    if resolved_student_id and data:
        all_lesson_ids = []
        for c in data:
            for ch in c.get("chapters", []):
                for l in ch.get("lessons", []):
                    if l.get("id"):
                        all_lesson_ids.append(l["id"])
        if all_lesson_ids:
            prog_res = supabase.table("lesson_progress")\
                .select("lesson_id")\
                .eq("student_id", resolved_student_id)\
                .eq("status", "completed")\
                .in_("lesson_id", all_lesson_ids)\
                .execute()
            completed_set = {p["lesson_id"] for p in (prog_res.data or [])}
            for c in data:
                lesson_ids = []
                for ch in c.get("chapters", []):
                    for l in ch.get("lessons", []):
                        if l.get("id"):
                            lesson_ids.append(l["id"])
                total = len(lesson_ids)
                done = sum(1 for lid in lesson_ids if lid in completed_set)
                c["progress"] = round(done / total * 100) if total > 0 else 0
                c["completed_lessons"] = done
                c["total_lessons"] = total
        else:
            for c in data:
                c["progress"] = 0
                c["completed_lessons"] = 0
                c["total_lessons"] = 0
    
    return data

@router.post("/heartbeat")
async def student_heartbeat(
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    """
    Update student's last_active_at timestamp.
    Called periodically from the student/parent dashboard or LMS.
    """
    try:
        resolved_student_id = x_active_student_id
        if current_user.get("role") == "student":
            resolved_student_id = current_user["id"]
        elif current_user.get("role") == "parent":
            if not resolved_student_id:
                return {"status": "skipped", "reason": "No active student"}
            check = supabase.table("students").select("parent_id").eq("id", resolved_student_id).execute()
            if not check.data or check.data[0]["parent_id"] != current_user["id"]:
                return {"status": "error", "message": "Unauthorized student heartbeat"}
        else:
            return {"status": "skipped", "reason": "Not a student or parent"}

        from datetime import datetime
        now = datetime.now().isoformat()
        supabase.table("students").update({"last_active_at": now}).eq("id", resolved_student_id).execute()
        
        return {"status": "success", "timestamp": now}
    except Exception as e:
        print(f"DEBUG: Heartbeat Error: {str(e)}")
        return {"status": "error", "message": str(e)}

@router.get("/stats")
async def get_lms_stats(
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = x_active_student_id
    if current_user.get("role") == "student":
        resolved_student_id = current_user["id"]
    elif current_user.get("role") == "parent":
        if not resolved_student_id:
            return {"streak": 0, "rank": None, "total_students": 0, "points": 0, "last_week_dates": []}
        student_check = supabase.table("students").select("parent_id").eq("id", resolved_student_id).execute()
        if not student_check.data or student_check.data[0].get("parent_id") != current_user["id"]:
            return {"streak": 0, "rank": None, "total_students": 0, "points": 0, "last_week_dates": []}
    else:
        return {"streak": 0, "rank": None, "total_students": 0, "points": 0, "last_week_dates": []}

    from datetime import datetime, timedelta, date

    # Get completed lessons for this student
    prog_res = supabase.table("lesson_progress")\
        .select("lesson_id, completed_at")\
        .eq("student_id", resolved_student_id)\
        .eq("status", "completed")\
        .order("completed_at", desc=True)\
        .execute()
    completed = prog_res.data or []
    points = len(completed)

    # Calculate streak (consecutive days)
    streak = 0
    if completed:
        dates = sorted(set(d["completed_at"][:10] for d in completed if d.get("completed_at")), reverse=True)
        if dates:
            today = date.today()
            latest = dates[0]
            if latest in (today.isoformat(), (today - timedelta(days=1)).isoformat()):
                anchor = date.fromisoformat(latest)
                for i, d in enumerate(dates):
                    if d == (anchor - timedelta(days=i)).isoformat():
                        streak += 1
                    else:
                        break
    
    # Last 7 days activity
    last_week_dates = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        last_week_dates.append({"date": d, "active": d in {c["completed_at"][:10] for c in completed if c.get("completed_at")}})

    # Calculate rank
    rank = None
    total_students = 0
    all_students = supabase.table("lesson_progress")\
        .select("student_id")\
        .eq("status", "completed")\
        .execute()
    if all_students.data:
        counts: dict = {}
        for p in all_students.data:
            sid = p.get("student_id")
            if sid:
                counts[sid] = counts.get(sid, 0) + 1
        total_students = len(counts)
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        student_count = counts.get(resolved_student_id, 0)
        for idx, (sid, cnt) in enumerate(sorted_counts, 1):
            if sid == resolved_student_id:
                rank = idx
                break

    return {
        "streak": streak,
        "rank": rank,
        "total_students": total_students,
        "points": points,
        "last_week_dates": last_week_dates
    }


@router.get("/courses/{course_id}")
async def get_course_detail(
    course_id: UUID,
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    res = supabase.table("courses").select("*, chapters(*, lessons(*))").eq("id", str(course_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Course tidak ditemukan")
    
    course = res.data[0]
    
    # Sort chapters and lessons
    if "chapters" in course:
        course["chapters"] = sorted(course["chapters"], key=lambda x: x.get("sort_order", 0))
        for chapter in course["chapters"]:
            if "lessons" in chapter:
                chapter["lessons"] = sorted(chapter["lessons"], key=lambda x: x.get("sort_order", 0))

    # Add completed lesson IDs for the current student
    resolved_student_id = x_active_student_id
    if current_user.get("role") == "student":
        resolved_student_id = current_user["id"]
    elif current_user.get("role") == "parent" and not x_active_student_id:
        resolved_student_id = None

    course["completed_lesson_ids"] = []
    if resolved_student_id:
        all_lesson_ids = []
        for ch in course.get("chapters", []):
            for l in ch.get("lessons", []):
                if l.get("id"):
                    all_lesson_ids.append(l["id"])
        if all_lesson_ids:
            prog_res = supabase.table("lesson_progress")\
                .select("lesson_id")\
                .eq("student_id", resolved_student_id)\
                .eq("status", "completed")\
                .in_("lesson_id", all_lesson_ids)\
                .execute()
            course["completed_lesson_ids"] = [p["lesson_id"] for p in (prog_res.data or [])]

    # Calculate progress
    total = len(all_lesson_ids) if all_lesson_ids else 0
    done = len(course["completed_lesson_ids"])
    course["progress"] = round(done / total * 100) if total > 0 else 0
    course["completed_lessons"] = done
    course["total_lessons"] = total

    return course

# --- Lessons ---

async def check_lesson_access(
    lesson_id: UUID,
    current_user: dict,
    x_active_student_id: Optional[str]
) -> str:
    if current_user.get("role") == "admin":
        return ""
        
    student_id = x_active_student_id
    if current_user.get("role") == "student":
        student_id = current_user["id"]
        student_status = current_user.get("status")
    else:
        student_status = None
        if student_id:
            s_res = supabase.table("students").select("status").eq("id", student_id).execute()
            student_status = s_res.data[0].get("status") if s_res.data else None
            
    if student_status == "preview":
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak: Akun Anda dalam status preview. Silakan lakukan pembayaran untuk mengakses materi kelas."
        )
        
    if not student_id:
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak: Enrollment aktif diperlukan"
        )
        
    if current_user.get("role") == "parent":
        check = supabase.table("students").select("parent_id").eq("id", str(student_id)).execute()
        if not check.data or check.data[0].get("parent_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Akses ditolak: Siswa tidak terhubung dengan akun orang tua Anda")

    lesson_res = supabase.table("lessons").select("chapter_id").eq("id", str(lesson_id)).execute()
    if not lesson_res.data:
        raise HTTPException(status_code=404, detail="Lesson tidak ditemukan")
        
    chapter_id = lesson_res.data[0].get("chapter_id")
    chapter_res = supabase.table("chapters").select("course_id").eq("id", chapter_id).execute()
    if not chapter_res.data:
        raise HTTPException(status_code=404, detail="Course tidak ditemukan untuk chapter ini")
        
    course_id = chapter_res.data[0].get("course_id")
    
    enroll_check = supabase.table("enrollments")\
        .select("status")\
        .eq("student_id", str(student_id))\
        .eq("course_id", course_id)\
        .execute()
        
    if not enroll_check.data or enroll_check.data[0].get("status") != "active":
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak: Anda tidak memiliki enrollment aktif untuk kursus ini"
        )
    return str(student_id)


@router.get("/lessons/{lesson_id}")
async def get_lesson_detail(
    lesson_id: UUID,
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    await check_lesson_access(lesson_id, current_user, x_active_student_id)
    res = supabase.table("lessons").select("*").eq("id", str(lesson_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Lesson tidak ditemukan")
    return res.data[0]


@router.get("/lessons/{lesson_id}/content")
async def get_lesson_content(
    lesson_id: UUID,
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    await check_lesson_access(lesson_id, current_user, x_active_student_id)
    res = supabase.table("lesson_contents").select("*").eq("lesson_id", str(lesson_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Konten lesson tidak ditemukan")
    data = res.data[0]
    # Return body_md if available, fallback to legacy body
    if data.get("body_md"):
        data["body"] = None
    return data


# --- Enrollments ---

@router.get("/enrollments")
async def get_enrollments(
    student_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = student_id or x_active_student_id
    if not resolved_student_id:
        if current_user.get("role") == "student":
            resolved_student_id = current_user["id"]
        else:
            raise HTTPException(status_code=400, detail="student_id or X-Active-Student-Id header is required")

    if current_user.get("role") == "parent":
        check = supabase.table("students").select("parent_id").eq("id", resolved_student_id).execute()
        if not check.data or check.data[0].get("parent_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Akses ditolak: Siswa tidak terhubung dengan akun orang tua Anda")
    elif current_user.get("role") == "student" and resolved_student_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Akses ditolak: Anda tidak dapat melihat enrollment siswa lain")

    res = supabase.table("enrollments").select("*").eq("student_id", resolved_student_id).execute()
    return res.data or []


@router.post("/enrollments")
async def enroll_course(
    body: dict,
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    student_id = body.get("student_id") or x_active_student_id
    course_id = body.get("course_id")
    status = body.get("status", "active")

    if not student_id or not course_id:
        raise HTTPException(status_code=400, detail="student_id and course_id are required")

    if current_user.get("role") == "student" and student_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Akses ditolak: Anda tidak dapat mendaftarkan siswa lain")

    if current_user.get("role") == "parent":
        check = supabase.table("students").select("parent_id").eq("id", student_id).execute()
        if not check.data or check.data[0].get("parent_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Akses ditolak: Siswa tidak terhubung dengan akun orang tua Anda")

    student_check = supabase.table("students").select("id").eq("id", student_id).execute()
    if not student_check.data:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")

    # Fetch from new class_materi table
    cc_res = supabase.table("class_materi").select("class_id").eq("course_id", course_id).execute()
    class_ids = [cc["class_id"] for cc in cc_res.data] if cc_res.data else []

    # Also fetch from legacy classes.course_id just in case
    try:
        classes_res = supabase.table("classes").select("id").eq("course_id", course_id).execute()
        if classes_res.data:
            for c in classes_res.data:
                if c["id"] not in class_ids:
                    class_ids.append(c["id"])
    except Exception as e:
        print(f"Skipped legacy course_id lookup in classes table: {e}")

    has_paid_reg = False
    paid_class_id = None
    if class_ids:
        reg_details = supabase.table("registrations")\
            .select("class_id")\
            .eq("student_id", student_id)\
            .eq("status", "paid")\
            .execute()
        paid_class_ids = [r["class_id"] for r in reg_details.data if r.get("class_id")]
        for cid in paid_class_ids:
            if cid in class_ids:
                has_paid_reg = True
                paid_class_id = cid
                break

    if not has_paid_reg:
        course_check = supabase.table("courses").select("slug").eq("id", course_id).execute()
        if course_check.data and course_check.data[0]["slug"] == "scratch-dasar":
            any_reg = supabase.table("registrations")\
                .select("id", "class_id")\
                .eq("student_id", student_id)\
                .eq("status", "paid")\
                .execute()
            if any_reg.data:
                has_paid_reg = True
                paid_class_id = any_reg.data[0].get("class_id")

    if not has_paid_reg:
        raise HTTPException(
            status_code=402,
            detail="Pembayaran diperlukan: Anda belum membeli kelas untuk kursus ini"
        )

    existing = supabase.table("enrollments").select("*").eq("student_id", student_id).eq("course_id", course_id).execute()
    if existing.data:
        return existing.data[0]

    insert_data = {
        "student_id": student_id,
        "course_id": course_id,
        "status": status
    }
    if paid_class_id:
        insert_data["class_id"] = paid_class_id

    res = supabase.table("enrollments").insert(insert_data).execute()

    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal mendaftar kursus")
    return res.data[0]


# --- Progress ---

@router.post("/progress/{lesson_id}")
async def update_lesson_progress(
    lesson_id: UUID,
    student_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = student_id or x_active_student_id
    if not resolved_student_id:
        if current_user.get("role") == "student":
            resolved_student_id = current_user["id"]
        else:
            raise HTTPException(status_code=400, detail="student_id or X-Active-Student-Id header is required")

    if current_user.get("role") == "parent":
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak: Orang tua tidak dapat mengubah progress pembelajaran anak (mode read-only)"
        )

    if current_user.get("role") == "student" and resolved_student_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Akses ditolak: Anda tidak dapat mengubah progress siswa lain")

    existing = supabase.table("lesson_progress").select("*").eq("student_id", resolved_student_id).eq("lesson_id", str(lesson_id)).execute()
    if existing.data:
        return existing.data[0]

    res = supabase.table("lesson_progress").insert({
        "student_id": resolved_student_id,
        "lesson_id": str(lesson_id),
        "status": "completed"
    }).execute()
    return res.data[0]


@router.get("/progress/{lesson_id}")
async def get_lesson_progress(
    lesson_id: UUID,
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = x_active_student_id
    if current_user.get("role") == "student":
        resolved_student_id = current_user["id"]
    elif current_user.get("role") == "parent":
        if not resolved_student_id:
            return {"completed": False}
        check = supabase.table("students").select("parent_id").eq("id", resolved_student_id).execute()
        if not check.data or check.data[0].get("parent_id") != current_user["id"]:
            return {"completed": False}
    else:
        return {"completed": False}

    if not resolved_student_id:
        return {"completed": False}

    existing = supabase.table("lesson_progress").select("status")\
        .eq("student_id", resolved_student_id)\
        .eq("lesson_id", str(lesson_id))\
        .execute()
    completed = len(existing.data) > 0 and existing.data[0].get("status") == "completed"
    return {"completed": completed}


# --- Dashboard ---

@router.get("/dashboard")
async def get_lms_dashboard(
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = x_active_student_id
    student_name = current_user.get("name", "Student")
    
    if current_user.get("role") == "student":
        resolved_student_id = current_user["id"]
    elif current_user.get("role") == "parent":
        if not resolved_student_id:
            raise HTTPException(status_code=400, detail="X-Active-Student-Id header is required for parent lms access")
        
        student_check = supabase.table("students").select("name, parent_id").eq("id", resolved_student_id).execute()
        if not student_check.data or student_check.data[0].get("parent_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Akses ditolak: Siswa tidak terhubung dengan akun orang tua Anda")
        student_name = student_check.data[0]["name"]
    else:
        raise HTTPException(status_code=403, detail="Akses ditolak: Hanya siswa atau orang tua yang dapat mengakses LMS")

    enrollments_res = supabase.table("enrollments").select("course_id").eq("student_id", resolved_student_id).execute()
    enrollment_list = enrollments_res.data or []
    course_ids = [e["course_id"] for e in enrollment_list]
    
    enrolled_courses = []
    if course_ids:
        for cid in course_ids:
            c_res = supabase.table("courses").select("*, chapters(*, lessons(*))").eq("id", cid).execute()
            if c_res.data:
                enrolled_courses.append(c_res.data[0])
    # Calculate completed lessons/progress
    progress_res = supabase.table("lesson_progress")\
        .select("status")\
        .eq("student_id", resolved_student_id)\
        .eq("status", "completed")\
        .execute()
    completed_lessons = len(progress_res.data) if progress_res.data else 0
    
    # Calculate avg quiz score
    quiz_res = supabase.table("quiz_submissions")\
        .select("percentage")\
        .eq("student_id", resolved_student_id)\
        .execute()
    quiz_scores = [q["percentage"] for q in quiz_res.data] if quiz_res.data else []
    avg_score = sum(quiz_scores) / len(quiz_scores) if quiz_scores else 0.0

    # Fetch attendance summary
    present_count = 0
    permission_count = 0
    absent_count = 0
    attendance_text = "0 hadir, 0 izin, 0 alfa"
    att_res = supabase.table("attendances").select("status").eq("student_id", resolved_student_id).execute()
    if att_res.data:
        present_count = sum(1 for a in att_res.data if a["status"] in ("present", "late"))
        permission_count = sum(1 for a in att_res.data if a["status"] == "permission")
        absent_count = sum(1 for a in att_res.data if a["status"] == "absent")
        attendance_text = f"{present_count} hadir, {permission_count} izin, {absent_count} alfa"

    # Fetch latest project/assignment submission
    last_project_title = "-"
    sub_res = supabase.table("assignment_submissions")\
        .select("assignment_id")\
        .eq("student_id", resolved_student_id)\
        .order("submitted_at", desc=True)\
        .limit(1)\
        .execute()
    if sub_res.data:
        assign_id = sub_res.data[0]["assignment_id"]
        assign_res = supabase.table("assignments").select("title").eq("id", assign_id).execute()
        if assign_res.data:
            last_project_title = assign_res.data[0]["title"]

    # Fetch actual schedules
    upcoming_meetings = []
    enroll_full = supabase.table("enrollments").select("id, course_id").eq("student_id", resolved_student_id).execute()
    enrollment_ids = [e["id"] for e in (enroll_full.data or [])]
    
    if enrollment_ids:
        schedules_res = supabase.table("schedules")\
            .select("*")\
            .in_("enrollment_id", enrollment_ids)\
            .order("start_time")\
            .execute()
        
        for s in (schedules_res.data or []):
            mentor_name = "Mentor GenKiddo"
            if s.get("mentor_id"):
                mentor_res = supabase.table("mentors").select("parent_id").eq("id", s["mentor_id"]).execute()
                if mentor_res.data:
                    parent_res = supabase.table("parents").select("name").eq("id", mentor_res.data[0]["parent_id"]).execute()
                    if parent_res.data:
                        mentor_name = parent_res.data[0]["name"]
            
            course_title = "Materi Belajar"
            if s.get("course_id"):
                c_res = supabase.table("courses").select("title").eq("id", s["course_id"]).execute()
                if c_res.data:
                    course_title = c_res.data[0]["title"]
            
            upcoming_meetings.append({
                "id": s["id"],
                "title": s["title"],
                "class_type": s["class_type"],
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "location": s.get("location") or "",
                "zoom_join_url": s.get("zoom_join_url") or "",
                "status": s["status"],
                "mentor_name": mentor_name,
                "course_title": course_title
            })

    # Fetch session reports (submitted status only)
    session_reports = []
    rep_session_res = supabase.table("session_reports")\
        .select("*")\
        .eq("student_id", resolved_student_id)\
        .eq("status", "submitted")\
        .order("created_at", desc=True)\
        .execute()
        
    for r in (rep_session_res.data or []):
        session_title = "Sesi Belajar"
        session_date = None
        if r.get("schedule_id"):
            sched_res = supabase.table("schedules").select("title, start_time").eq("id", r["schedule_id"]).execute()
            if sched_res.data:
                session_title = sched_res.data[0]["title"]
                session_date = sched_res.data[0]["start_time"]
                
        mentor_name = "Mentor GenKiddo"
        if r.get("mentor_id"):
            mentor_res = supabase.table("mentors").select("parent_id").eq("id", r["mentor_id"]).execute()
            if mentor_res.data:
                parent_res = supabase.table("parents").select("name").eq("id", mentor_res.data[0]["parent_id"]).execute()
                if parent_res.data:
                    mentor_name = parent_res.data[0]["name"]
                    
        session_reports.append({
            "id": r["id"],
            "schedule_id": r["schedule_id"],
            "session_title": session_title,
            "session_date": session_date,
            "mentor_name": mentor_name,
            "material_summary": r["material_summary"],
            "understanding_score": r["understanding_score"],
            "logic_score": r["logic_score"],
            "creativity_score": r["creativity_score"],
            "independence_score": r["independence_score"],
            "digital_ethics_score": r["digital_ethics_score"],
            "mentor_notes": r["mentor_notes"],
            "recommendation": r.get("recommendation") or ""
        })

    # Fetch approved final reports and issued certificates
    reports = []
    certificates = []
    for e in (enroll_full.data or []):
        course_title = "Kursus"
        c_res = supabase.table("courses").select("title").eq("id", e["course_id"]).execute()
        if c_res.data:
            course_title = c_res.data[0]["title"]
            
        rep_res = supabase.table("final_reports").select("*").eq("enrollment_id", e["id"]).execute()
        if rep_res.data and rep_res.data[0].get("status") in ("approved", "published"):
            rep = rep_res.data[0]
            rep["course_title"] = course_title
            
            mentor_name = "Mentor GenKiddo"
            if rep.get("mentor_id"):
                mentor_res = supabase.table("mentors").select("parent_id").eq("id", rep["mentor_id"]).execute()
                if mentor_res.data:
                    parent_res = supabase.table("parents").select("name").eq("id", mentor_res.data[0]["parent_id"]).execute()
                    if parent_res.data:
                        mentor_name = parent_res.data[0]["name"]
            rep["mentor_name"] = mentor_name
            reports.append(rep)
            
        cert_res = supabase.table("certificates").select("*").eq("enrollment_id", e["id"]).execute()
        if cert_res.data and cert_res.data[0].get("status") in ("issued", "approved"):
            cert = cert_res.data[0]
            cert["course_title"] = course_title
            certificates.append(cert)

    # Calculate total lessons across all enrolled courses
    total_lessons = 0
    for c in enrolled_courses:
        if "chapters" in c:
            for ch in c["chapters"]:
                total_lessons += len(ch.get("lessons") or [])
    progress_val = round(completed_lessons / total_lessons * 100) if total_lessons > 0 else 0

    return {
        "student_name": student_name,
        "enrolled_courses": enrolled_courses,
        "stats": {
            "progress": progress_val,
            "completed_chapters": completed_lessons,
            "completed_sessions": completed_lessons,
            "avg_quiz_score": round(avg_score, 1),
            "present_count": present_count,
            "permission_count": permission_count,
            "absent_count": absent_count,
            "attendance_text": attendance_text,
            "last_project_title": last_project_title
        },
        "assignments": {
            "pretest": round(avg_score, 1) if avg_score > 0 else "-",
            "posttest": "-",
            "quiz": round(avg_score, 1) if avg_score > 0 else "-",
            "final_project": "-"
        },
        "upcoming_meetings": upcoming_meetings,
        "session_reports": session_reports,
        "final_reports": reports,
        "certificates": certificates
    }

# --- Student Assignment Submissions ---

def resolve_and_verify_student(current_user: dict, x_active_student_id: Optional[str], is_write: bool = False) -> str:
    resolved_student_id = x_active_student_id
    if current_user.get("role") == "student":
        resolved_student_id = current_user["id"]
    elif current_user.get("role") == "parent":
        if is_write:
            raise HTTPException(
                status_code=403,
                detail="Akses ditolak: Orang tua tidak dapat mengumpulkan tugas atau mengubah progres anak (mode read-only)"
            )
        if not resolved_student_id:
            raise HTTPException(status_code=400, detail="X-Active-Student-Id header is required for parent lms access")
        
        student_check = supabase.table("students").select("parent_id").eq("id", resolved_student_id).execute()
        if not student_check.data or student_check.data[0].get("parent_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Akses ditolak: Siswa tidak terhubung dengan akun orang tua Anda")
    else:
        raise HTTPException(status_code=403, detail="Akses ditolak: Hanya siswa atau orang tua yang dapat mengakses LMS")
        
    # Check student status
    student_res = supabase.table("students").select("status").eq("id", resolved_student_id).execute()
    if not student_res.data:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    student_status = student_res.data[0].get("status")
    if student_status == "preview":
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak: Akun dalam status preview. Silakan lakukan pembayaran untuk mengakses fitur ini."
        )
        
    return resolved_student_id

class AssignmentSubmitRequest(BaseModel):
    submission_url: str
    notes: Optional[str] = None

@router.get("/assignments")
async def list_student_assignments(
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    student_id = resolve_and_verify_student(current_user, x_active_student_id)
    
    # Get enrollments for student to know which classes (batches) they belong to
    enroll_res = supabase.table("enrollments").select("class_id").eq("student_id", student_id).execute()
    class_ids = [e["class_id"] for e in enroll_res.data if e.get("class_id")]
    
    if not class_ids:
        return {"data": []}
        
    # Get assignments for those classes
    assignments_res = supabase.table("assignments").select("*").in_("batch_id", class_ids).execute()
    assignments = assignments_res.data or []
    
    result = []
    for a in assignments:
        # Check for submission
        sub_res = supabase.table("assignment_submissions")\
            .select("*")\
            .eq("assignment_id", a["id"])\
            .eq("student_id", student_id)\
            .execute()
        
        submission = sub_res.data[0] if sub_res.data else None
        
        # Get course title
        course_title = None
        if a.get("course_id"):
            c_res = supabase.table("courses").select("title").eq("id", a["course_id"]).execute()
            if c_res.data:
                course_title = c_res.data[0]["title"]
                
        # Get batch name
        batch_name = None
        if a.get("batch_id"):
            b_res = supabase.table("classes").select("display_name, name").eq("id", a["batch_id"]).execute()
            if b_res.data:
                batch_name = b_res.data[0].get("display_name") or b_res.data[0].get("name")
                
        result.append({
            "id": a["id"],
            "title": a["title"],
            "description": a["description"],
            "assignment_type": a["assignment_type"],
            "due_at": a["due_at"],
            "attachment_url": a["attachment_url"],
            "status": a["status"],
            "course_title": course_title,
            "batch_name": batch_name,
            "submission": submission
        })
        
    return {"data": result}

@router.post("/assignments/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: UUID,
    body: AssignmentSubmitRequest,
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    student_id = resolve_and_verify_student(current_user, x_active_student_id, is_write=True)
    
    # Check if assignment exists
    assign_res = supabase.table("assignments").select("id, batch_id").eq("id", str(assignment_id)).execute()
    if not assign_res.data:
        raise HTTPException(status_code=404, detail="Assignment tidak ditemukan")
        
    # Verify student is enrolled in this batch
    batch_id = assign_res.data[0]["batch_id"]
    enroll_res = supabase.table("enrollments").select("id").eq("student_id", student_id).eq("class_id", batch_id).execute()
    if not enroll_res.data:
        raise HTTPException(status_code=403, detail="Akses ditolak: Anda tidak terdaftar di kelas (batch) assignment ini")
        
    payload = {
        "assignment_id": str(assignment_id),
        "student_id": student_id,
        "submission_url": body.submission_url.strip(),
        "notes": body.notes
    }
    
    # Upsert submission on conflict of assignment_id + student_id
    res = supabase.table("assignment_submissions").upsert(payload, on_conflict="assignment_id, student_id").execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menyimpan tugas")
        
    return {"message": "Tugas berhasil dikumpulkan", "data": res.data[0]}


# ─── Student Achievements ─────────────────────────

@router.get("/achievements")
async def get_student_achievements(
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = x_active_student_id
    if current_user.get("role") == "student":
        resolved_student_id = current_user["id"]
    elif current_user.get("role") == "parent":
        if not resolved_student_id:
            return {"achievements": [], "recent": []}
        check = supabase.table("students").select("parent_id").eq("id", resolved_student_id).execute()
        if not check.data or check.data[0].get("parent_id") != current_user["id"]:
            return {"achievements": [], "recent": []}
    else:
        return {"achievements": [], "recent": []}

    if not resolved_student_id:
        return {"achievements": [], "recent": []}

    # Get all achievements
    all_ach = supabase.table("achievements").select("*").eq("is_active", True).order("sort_order").execute()
    achievements = all_ach.data or []

    # Get student's earned achievement IDs
    earned_res = supabase.table("student_achievements").select("achievement_id, earned_at").eq("student_id", resolved_student_id).execute()
    earned_map = {e["achievement_id"]: e["earned_at"] for e in (earned_res.data or [])}

    # Get stats to evaluate conditions
    lesson_count = 0
    streak_days = 0
    quiz_count = 0
    quiz_perfect = 0
    completed_courses = set()

    prog_res = supabase.table("lesson_progress").select("lesson_id, status").eq("student_id", resolved_student_id).eq("status", "completed").execute()
    lesson_count = len(prog_res.data or [])

    quiz_res = supabase.table("quiz_submissions").select("percentage").eq("student_id", resolved_student_id).execute()
    if quiz_res.data:
        quiz_count = len(quiz_res.data)
        quiz_perfect = sum(1 for q in quiz_res.data if q["percentage"] == 100)

    # Check course completion (all lessons completed in a course)
    enroll_res = supabase.table("enrollments").select("course_id").eq("student_id", resolved_student_id).eq("status", "active").execute()
    for e in (enroll_res.data or []):
        c_res = supabase.table("courses").select("*, chapters(*, lessons(*))").eq("id", e["course_id"]).execute()
        if c_res.data:
            course = c_res.data[0]
            all_ids = [l["id"] for ch in course.get("chapters", []) for l in ch.get("lessons", []) if l.get("id")]
            done_ids = set(p["lesson_id"] for p in (prog_res.data or []) if p.get("lesson_id"))
            if all_ids and all(lid in done_ids for lid in all_ids):
                completed_courses.add(e["course_id"])

    # Check streak
    streak_res = supabase.table("lesson_progress").select("completed_at").eq("student_id", resolved_student_id).eq("status", "completed").order("completed_at", desc=True).execute()
    if streak_res.data:
        from datetime import date, timedelta
        dates = sorted(set(d["completed_at"][:10] for d in streak_res.data if d.get("completed_at")), reverse=True)
        if dates:
            today = date.today()
            latest = dates[0]
            if latest in (today.isoformat(), (today - timedelta(days=1)).isoformat()):
                anchor = date.fromisoformat(latest)
                for i, d in enumerate(dates):
                    if d == (anchor - timedelta(days=i)).isoformat():
                        streak_days += 1
                    else:
                        break

    # Evaluate achievements
    result = []
    for ach in achievements:
        earned = ach["id"] in earned_map
        met = False
        ct = ach["condition_type"]
        cv = ach["condition_value"]

        if ct == "lesson_count":
            met = lesson_count >= cv
        elif ct == "streak_days":
            met = streak_days >= cv
        elif ct == "quiz_score":
            met = quiz_perfect >= cv
        elif ct == "quiz_count":
            met = quiz_count >= cv
        elif ct == "complete_course":
            met = len(completed_courses) >= cv

        if met and not earned:
            # Auto-earn
            supabase.table("student_achievements").insert({
                "student_id": resolved_student_id,
                "achievement_id": ach["id"]
            }).execute()
            earned = True
            earned_map[ach["id"]] = None

        result.append({
            "id": ach["id"],
            "title": ach["title"],
            "description": ach["description"],
            "icon": ach["icon"],
            "color": ach["color"],
            "category": ach["category"],
            "condition_type": ct,
            "condition_value": cv,
            "earned": earned,
            "earned_at": str(earned_map.get(ach["id"], "")) if earned else None,
        })

    recent = [a for a in result if a["earned"]][:4]

    return {"achievements": result, "recent": recent}


# ─── Leaderboard ────────────────────────────────────

@router.get("/leaderboard")
async def get_leaderboard(
    period: str = Query("all", regex="^(today|week|month|all)$"),
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = x_active_student_id
    if current_user.get("role") == "student":
        resolved_student_id = current_user["id"]
    elif current_user.get("role") == "parent":
        if not resolved_student_id:
            resolved_student_id = None
        else:
            check = supabase.table("students").select("parent_id").eq("id", resolved_student_id).execute()
            if not check.data or check.data[0].get("parent_id") != current_user["id"]:
                resolved_student_id = None

    from datetime import date, timedelta

    # Filter by period
    date_filter = None
    if period == "today":
        date_filter = date.today().isoformat()
    elif period == "week":
        date_filter = (date.today() - timedelta(days=7)).isoformat()
    elif period == "month":
        date_filter = (date.today() - timedelta(days=30)).isoformat()

    # Get all students with completed lesson counts
    query = supabase.table("lesson_progress").select("student_id").eq("status", "completed")
    if date_filter:
        query = query.gte("completed_at", date_filter)
    prog_data = query.execute()
    prog_rows = prog_data.data or []

    # Count per student
    counts: dict = {}
    for r in prog_rows:
        sid = r.get("student_id")
        if sid:
            counts[sid] = counts.get(sid, 0) + 1

    if not counts:
        return {"leaderboard": [], "current_user": None, "period": period}

    # Sort by count descending
    sorted_students = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    # Get student details
    student_ids = [s[0] for s in sorted_students]
    students_res = supabase.table("students").select("id, name, username, created_at, status").in_("id", student_ids).execute()
    students_map = {s["id"]: s for s in (students_res.data or []) if s.get("status") == "active"}

    # Recalculate after filtering non-active
    leaderboard = []
    rank = 0
    for sid, pts in sorted_students:
        s = students_map.get(sid)
        if not s:
            continue
        rank += 1
        points = pts * 10

        # Calculate streak (same logic as stats)
        streak = 0
        streak_res = supabase.table("lesson_progress").select("completed_at")\
            .eq("student_id", sid).eq("status", "completed")\
            .order("completed_at", desc=True).execute()
        if streak_res.data:
            streak_dates = sorted(set(d["completed_at"][:10] for d in streak_res.data if d.get("completed_at")), reverse=True)
            if streak_dates:
                today = date.today()
                latest = streak_dates[0]
                if latest in (today.isoformat(), (today - timedelta(days=1)).isoformat()):
                    anchor = date.fromisoformat(latest)
                    for i, d in enumerate(streak_dates):
                        if d == (anchor - timedelta(days=i)).isoformat():
                            streak += 1
                        else:
                            break

        level = max(1, pts // 3 + 1)
        titles = ["Petualang Baru", "Kadet Bintang", "Penjelajah Bulan", "Penjelajah Mars", "Penjelajah Galaksi", "Penguasa Semesta"]
        title_idx = min(level - 1, len(titles) - 1)

        leaderboard.append({
            "rank": rank,
            "student_id": sid,
            "name": s["name"],
            "points": points,
            "streak": streak,
            "level": level,
            "title": titles[title_idx],
        })

    # Current user info (always include even if 0 points)
    current_user_entry = None
    if resolved_student_id:
        for entry in leaderboard:
            if entry["student_id"] == resolved_student_id:
                current_user_entry = {**entry}
                break
        if not current_user_entry:
            s_res = supabase.table("students").select("name").eq("id", resolved_student_id).execute()
            s_name = s_res.data[0]["name"] if s_res.data else "Siswa"
            current_user_entry = {
                "rank": len(leaderboard) + 1,
                "student_id": resolved_student_id,
                "name": s_name,
                "points": 0,
                "streak": 0,
                "level": 1,
                "title": "Petualang Baru",
            }

    return {"leaderboard": leaderboard, "current_user": current_user_entry, "period": period}
