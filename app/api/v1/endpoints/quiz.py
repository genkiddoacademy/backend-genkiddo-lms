import random
from fastapi import APIRouter, HTTPException, Depends, Query, Header
from app.api.v1.endpoints.auth import get_current_user, require_role
from app.core.postgre import supabase
from app.schemas.quiz import (
    QuizCreate, QuizUpdate, QuizResponse, QuizWithQuestions,
    QuestionCreate, QuestionUpdate, QuestionResponse,
    QuizSubmitRequest, QuizSubmitResponse, QuizSubmissionResponse
)
from app.services.grading import grade_question, calculate_total_marks, check_passing
from typing import List, Optional
from uuid import UUID
from datetime import datetime

admin_router = APIRouter(prefix="/admin", tags=["Admin Quiz"])
lms_router = APIRouter(prefix="/lms", tags=["LMS Quiz"])

admin_required = require_role("admin")

# --- ADMIN ENDPOINTS ---

@admin_router.post("/lessons/{lesson_id}/quiz", response_model=QuizResponse)
async def create_quiz(
    lesson_id: UUID,
    body: QuizCreate,
    current_user: dict = Depends(admin_required)
):
    try:
        # Check if quiz already exists for this lesson
        existing = supabase.table("quizzes").select("*").eq("lesson_id", str(lesson_id)).execute()
        if existing.data:
            # Update existing instead of creating new to handle frontend retries/states
            data = body.model_dump(exclude_none=True)
            data.pop("lesson_id", None)
            res = supabase.table("quizzes").update(data).eq("lesson_id", str(lesson_id)).execute()
            return res.data[0]

        data = body.model_dump(exclude_none=True)
        # Filter out lesson_id if it exists in body to avoid conflict
        data.pop("lesson_id", None)
        data["lesson_id"] = str(lesson_id)
        
        # Ensure default values if missing
        if "title" not in data or not data["title"]:
            data["title"] = "Quiz Baru"
        if "passing_percentage" not in data:
            data["passing_percentage"] = 70.0
            
        res = supabase.table("quizzes").insert(data).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Gagal membuat quiz di database")
        
        quiz = res.data[0]
        # Update lesson to reference this quiz
        supabase.table("lessons").update({"quiz_id": quiz["id"]}).eq("id", str(lesson_id)).execute()
        
        return quiz
    except Exception as e:
        import traceback
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.post("/quizzes/{quiz_id}/questions", response_model=QuestionResponse)
async def create_question(
    quiz_id: UUID,
    body: QuestionCreate,
    current_user: dict = Depends(admin_required)
):
    try:
        data = body.model_dump(exclude_none=True)
        data["quiz_id"] = str(quiz_id)
        
        # Validation: question must be a list (BlockNote content)
        if "question" not in data or data["question"] is None:
            data["question"] = []
            
        res = supabase.table("questions").insert(data).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Gagal membuat pertanyaan")
        return res.data[0]
    except Exception as e:
        import traceback
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/lessons/{lesson_id}/quiz", response_model=QuizWithQuestions)
async def get_quiz_admin(
    lesson_id: UUID,
    current_user: dict = Depends(admin_required)
):
    try:
        res = supabase.table("quizzes").select("*").eq("lesson_id", str(lesson_id)).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Quiz tidak ditemukan")
        
        quiz = res.data[0]
        questions_res = supabase.table("questions").select("*").eq("quiz_id", quiz["id"]).execute()
        quiz["questions"] = sorted(questions_res.data or [], key=lambda x: x.get("sort_order", 0))
        
        return quiz
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.put("/quizzes/{quiz_id}", response_model=QuizResponse)
async def update_quiz(
    quiz_id: UUID,
    body: QuizUpdate,
    current_user: dict = Depends(admin_required)
):
    try:
        data = body.model_dump(exclude_none=True)
        res = supabase.table("quizzes").update(data).eq("id", str(quiz_id)).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Quiz tidak ditemukan")
        return res.data[0]
    except Exception as e:
        import traceback
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.delete("/quizzes/{quiz_id}")
async def delete_quiz(
    quiz_id: UUID,
    current_user: dict = Depends(admin_required)
):
    res = supabase.table("quizzes").delete().eq("id", str(quiz_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Quiz tidak ditemukan")
    return {"message": "Quiz berhasil dihapus"}

@admin_router.post("/quizzes/{quiz_id}/questions", response_model=QuestionResponse)
async def create_question(
    quiz_id: UUID,
    body: QuestionCreate,
    current_user: dict = Depends(admin_required)
):
    data = body.model_dump(exclude_none=True)
    data["quiz_id"] = str(quiz_id)
    res = supabase.table("questions").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat pertanyaan")
    return res.data[0]

@admin_router.put("/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: UUID,
    body: QuestionUpdate,
    current_user: dict = Depends(admin_required)
):
    res = supabase.table("questions").update(body.model_dump(exclude_none=True)).eq("id", str(question_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Pertanyaan tidak ditemukan")
    return res.data[0]

@admin_router.delete("/questions/{question_id}")
async def delete_question(
    question_id: UUID,
    current_user: dict = Depends(admin_required)
):
    res = supabase.table("questions").delete().eq("id", str(question_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Pertanyaan tidak ditemukan")
    return {"message": "Pertanyaan berhasil dihapus"}

@admin_router.post("/quizzes/{quiz_id}/questions/reorder")
async def reorder_questions(
    quiz_id: UUID,
    body: List[dict],
    current_user: dict = Depends(admin_required)
):
    for item in body:
        supabase.table("questions").update({"sort_order": item["sort_order"]}).eq("id", item["id"]).execute()
    return {"message": "Urutan pertanyaan berhasil diperbarui"}

@admin_router.get("/quizzes/{quiz_id}/submissions", response_model=List[QuizSubmissionResponse])
async def list_submissions(
    quiz_id: UUID,
    current_user: dict = Depends(admin_required)
):
    res = supabase.table("quiz_submissions").select("*").eq("quiz_id", str(quiz_id)).execute()
    return res.data or []

@admin_router.put("/submissions/{submission_id}/grade", response_model=QuizSubmissionResponse)
async def manual_grade_submission(
    submission_id: UUID,
    body: dict,
    current_user: dict = Depends(admin_required)
):
    sub_res = supabase.table("quiz_submissions").select("*").eq("id", str(submission_id)).execute()
    if not sub_res.data:
        raise HTTPException(status_code=404, detail="Submission tidak ditemukan")
    
    submission = sub_res.data[0]
    results = submission.get("result", [])
    
    question_id = str(body["question_id"])
    marks_earned = float(body["marks_earned"])
    
    updated = False
    for r in results:
        if r.get("question_id") == question_id:
            r["marks_earned"] = marks_earned
            r["is_correct"] = True if marks_earned > 0 else False
            updated = True
            break
            
    if not updated:
        results.append({"question_id": question_id, "marks_earned": marks_earned, "is_correct": True})
        
    new_score = sum(r.get("marks_earned", 0) for r in results)
    score_out_of = submission.get("score_out_of", 100)
    percentage = (new_score / score_out_of * 100) if score_out_of > 0 else 0
    
    update_data = {
        "result": results,
        "score": new_score,
        "percentage": percentage
    }
    
    res = supabase.table("quiz_submissions").update(update_data).eq("id", str(submission_id)).execute()
    return res.data[0]

# --- STUDENT ENDPOINTS ---

async def check_student_quiz_access(
    quiz_id: UUID,
    current_user: dict,
    student_id_param: Optional[str],
    x_active_student_id: Optional[str],
    is_write: bool = False
) -> str:
    student_id = student_id_param or x_active_student_id
    if current_user.get("role") == "student":
        student_id = current_user["id"]
        
    if not student_id:
        raise HTTPException(
            status_code=400,
            detail="student_id or X-Active-Student-Id header is required"
        )
        
    if is_write and current_user.get("role") == "parent":
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak: Orang tua tidak dapat mengirim jawaban quiz atau mengubah progres anak (mode read-only)"
        )
        
    if current_user.get("role") == "parent":
        check = supabase.table("students").select("parent_id").eq("id", str(student_id)).execute()
        if not check.data or check.data[0].get("parent_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Akses ditolak: Siswa tidak terhubung dengan akun orang tua Anda")
            
    quiz_res = supabase.table("quizzes").select("lesson_id").eq("id", str(quiz_id)).execute()
    if not quiz_res.data:
        raise HTTPException(status_code=404, detail="Quiz tidak ditemukan")
        
    lesson_id = quiz_res.data[0].get("lesson_id")
    if not lesson_id:
        raise HTTPException(status_code=404, detail="Lesson tidak ditemukan untuk quiz ini")
        
    lesson_res = supabase.table("lessons").select("chapter_id").eq("id", lesson_id).execute()
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


async def check_student_lesson_access(
    lesson_id: UUID,
    current_user: dict,
    student_id_param: Optional[str],
    x_active_student_id: Optional[str],
    is_write: bool = False
) -> str:
    student_id = student_id_param or x_active_student_id
    if current_user.get("role") == "student":
        student_id = current_user["id"]
        
    if not student_id:
        raise HTTPException(
            status_code=400,
            detail="student_id or X-Active-Student-Id header is required"
        )
        
    if is_write and current_user.get("role") == "parent":
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak: Orang tua tidak dapat mengubah progres anak (mode read-only)"
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


@lms_router.get("/lessons/{lesson_id}/quiz", response_model=QuizWithQuestions)
async def get_quiz_student(
    lesson_id: UUID,
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    await check_student_lesson_access(lesson_id, current_user, None, x_active_student_id, is_write=False)
    
    res = supabase.table("quizzes").select("*").eq("lesson_id", str(lesson_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Quiz tidak ditemukan")
    
    quiz = res.data[0]
    questions_res = supabase.table("questions").select("*").eq("quiz_id", quiz["id"]).execute()
    questions = questions_res.data or []
    
    if quiz.get("shuffle_questions"):
        random.shuffle(questions)
    
    limit = quiz.get("limit_questions_to")
    if limit and limit > 0:
        questions = questions[:limit]
        
    quiz["questions"] = questions
    return quiz


@lms_router.post("/quizzes/{quiz_id}/submit", response_model=QuizSubmitResponse)
async def submit_quiz(
    quiz_id: UUID,
    body: QuizSubmitRequest,
    student_id: Optional[UUID] = Query(None),
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = await check_student_quiz_access(
        quiz_id, current_user, str(student_id) if student_id else None, x_active_student_id, is_write=True
    )
    
    quiz_res = supabase.table("quizzes").select("*").eq("id", str(quiz_id)).execute()
    if not quiz_res.data:
        raise HTTPException(status_code=404, detail="Quiz tidak ditemukan")
    quiz = quiz_res.data[0]
    
    questions_res = supabase.table("questions").select("*").eq("quiz_id", str(quiz_id)).execute()
    questions_map = {str(q["id"]): q for q in (questions_res.data or [])}
    
    results = []
    total_earned = 0.0
    is_open_ended = False
    
    for ans in body.answers:
        q_id = str(ans.question_id)
        if q_id not in questions_map:
            continue
            
        question = questions_map[q_id]
        if question["type"] == "Open Ended":
            is_open_ended = True
            
        grade = grade_question(question, ans.answer, quiz.get("marks_to_cut", 0))
        results.append({
            "question_id": q_id,
            "answer": ans.answer,
            "is_correct": grade["is_correct"],
            "marks_earned": grade["marks_earned"]
        })
        total_earned += grade["marks_earned"]
        
    total_possible = calculate_total_marks(list(questions_map.values()), quiz.get("limit_questions_to"))
    percentage = (total_earned / total_possible * 100) if total_possible > 0 else 0
    is_passed = check_passing(percentage, quiz.get("passing_percentage", 0))
    
    attempts_res = supabase.table("quiz_submissions").select("id").eq("quiz_id", str(quiz_id)).eq("student_id", resolved_student_id).execute()
    attempt_number = len(attempts_res.data or []) + 1
    
    submission_data = {
        "quiz_id": str(quiz_id),
        "student_id": resolved_student_id,
        "score": total_earned,
        "score_out_of": total_possible,
        "percentage": percentage,
        "is_open_ended": is_open_ended,
        "result": results,
        "attempt_number": attempt_number,
        "submitted_at": datetime.now().isoformat()
    }
    
    supabase.table("quiz_submissions").insert(submission_data).execute()
    
    return {
        "score": total_earned,
        "percentage": percentage,
        "is_passed": is_passed,
        "result": results
    }


@lms_router.get("/quizzes/{quiz_id}/submissions", response_model=List[QuizSubmissionResponse])
async def student_submissions(
    quiz_id: UUID,
    student_id: Optional[UUID] = Query(None),
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = await check_student_quiz_access(
        quiz_id, current_user, str(student_id) if student_id else None, x_active_student_id, is_write=False
    )
    res = supabase.table("quiz_submissions").select("*").eq("quiz_id", str(quiz_id)).eq("student_id", resolved_student_id).execute()
    return res.data or []


@lms_router.post("/progress/{lesson_id}")
async def mark_progress(
    lesson_id: UUID,
    student_id: Optional[UUID] = Query(None),
    current_user: dict = Depends(get_current_user),
    x_active_student_id: Optional[str] = Header(None)
):
    resolved_student_id = await check_student_lesson_access(
        lesson_id, current_user, str(student_id) if student_id else None, x_active_student_id, is_write=True
    )
    
    existing = supabase.table("lesson_progress").select("*").eq("student_id", resolved_student_id).eq("lesson_id", str(lesson_id)).execute()
    
    data = {
        "student_id": resolved_student_id,
        "lesson_id": str(lesson_id),
        "status": "completed",
        "completed_at": datetime.now().isoformat()
    }
    
    if existing.data:
        res = supabase.table("lesson_progress").update(data).eq("id", existing.data[0]["id"]).execute()
    else:
        res = supabase.table("lesson_progress").insert(data).execute()
        
    return {"message": "Progress updated", "data": res.data[0] if res.data else None}
