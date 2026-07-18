import re
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from app.api.v1.endpoints.auth import require_role
from app.core.postgre import supabase
from app.schemas.courses import (
    CourseCreate, CourseUpdate, CourseResponse,
    ChapterCreate, ChapterUpdate, ChapterResponse,
    LessonCreate, LessonUpdate, LessonResponse,
    LessonContentUpdate, LessonContentResponse,
    LessonReorder, ChapterWithLessons, CourseListResponse
)
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.services.storage import storage_client
from app.core.config import settings
from app.services.gift_parser import parse_gift

router = APIRouter(prefix="/admin", tags=["Admin Courses"])
admin_required = require_role("admin")

# --- Courses ---

@router.get("/courses", response_model=CourseListResponse)
@router.get("/materi", response_model=CourseListResponse)
async def list_courses(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(admin_required)
):
    query = supabase.table("courses").select("*").eq("is_active", True)
    if status:
        query = query.eq("status", status)
    if category:
        query = query.eq("category", category)
    if level:
        query = query.eq("level", level)
    
    res = query.execute()
    data = res.data or []
    
    if search:
        s = search.lower()
        data = [c for c in data if s in c.get("title", "").lower() or (c.get("description") and s in c.get("description", "").lower())]
    
    total = len(data)
    start = (page - 1) * size
    end = start + size
    items = data[start:end]
    
    # Fetch first chapter and lesson for each course to allow direct linking
    for item in items:
        # Get first chapter
        chapters_res = supabase.table("chapters").select("id").eq("course_id", item["id"]).order("sort_order").limit(1).execute()
        if chapters_res.data:
            first_ch_id = chapters_res.data[0]["id"]
            item["first_chapter_id"] = first_ch_id
            
            # Get first lesson of that chapter
            lessons_res = supabase.table("lessons").select("id").eq("chapter_id", first_ch_id).order("sort_order").limit(1).execute()
            if lessons_res.data:
                item["first_lesson_id"] = lessons_res.data[0]["id"]
    
    return {
        "data": items,
        "total": total,
        "page": page,
        "size": size
    }

@router.post("/courses", response_model=CourseResponse)
@router.post("/materi", response_model=CourseResponse)
async def create_course(
    body: CourseCreate,
    current_user: dict = Depends(admin_required)
):
    try:
        data = body.model_dump(exclude_none=True)
        if "thumbnail" in data and data["thumbnail"]:
            if "uploads/" in data["thumbnail"]:
                idx = data["thumbnail"].find("uploads/")
                data["thumbnail"] = "/" + data["thumbnail"][idx:]
        res = supabase.table("courses").insert(data).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Gagal membuat course: Data tidak kembali dari database")
        return res.data[0]
    except Exception as e:
        print(f"DEBUG: Course Creation Error: {str(e)}")
        # Check for specific common errors
        detail = str(e)
        if "slug" in detail.lower() and "unique" in detail.lower():
            detail = "Slug course sudah digunakan. Silakan gunakan judul lain."
        
        raise HTTPException(status_code=400, detail=f"Gagal membuat course: {detail}")

@router.get("/courses/{course_id}", response_model=CourseResponse)
@router.get("/materi/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: UUID,
    current_user: dict = Depends(admin_required)
):
    res = supabase.table("courses").select("*").eq("id", str(course_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Course tidak ditemukan")
    return res.data[0]

@router.put("/courses/{course_id}", response_model=CourseResponse)
@router.put("/materi/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: UUID,
    body: CourseUpdate,
    current_user: dict = Depends(admin_required)
):
    data = body.model_dump(exclude_none=True)
    if "thumbnail" in data and data["thumbnail"]:
        if "uploads/" in data["thumbnail"]:
            idx = data["thumbnail"].find("uploads/")
            data["thumbnail"] = "/" + data["thumbnail"][idx:]
    res = supabase.table("courses").update(data).eq("id", str(course_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Course tidak ditemukan")
    return res.data[0]

@router.delete("/courses/{course_id}")
@router.delete("/materi/{course_id}")
async def delete_course(
    course_id: UUID,
    current_user: dict = Depends(admin_required)
):
    # Set is_active=false as requested
    res = supabase.table("courses").update({"is_active": False}).eq("id", str(course_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Course tidak ditemukan")
    return {"message": "Course berhasil dinonaktifkan"}

# --- Chapters ---

@router.get("/courses/{course_id}/chapters", response_model=List[ChapterWithLessons])
@router.get("/materi/{course_id}/chapters", response_model=List[ChapterWithLessons])
async def list_chapters(
    course_id: UUID,
    current_user: dict = Depends(admin_required)
):
    chapters_res = supabase.table("chapters").select("*").eq("course_id", str(course_id)).execute()
    chapters = chapters_res.data or []
    
    # Sort chapters by sort_order
    chapters = sorted(chapters, key=lambda x: x.get("sort_order", 0))
    
    for chapter in chapters:
        lessons_res = supabase.table("lessons").select("*").eq("chapter_id", chapter["id"]).execute()
        lessons = lessons_res.data or []
        chapter["lessons"] = sorted(lessons, key=lambda x: x.get("sort_order", 0))
        
    return chapters

@router.post("/courses/{course_id}/chapters", response_model=ChapterResponse)
@router.post("/materi/{course_id}/chapters", response_model=ChapterResponse)
async def create_chapter(
    course_id: UUID,
    body: ChapterCreate,
    current_user: dict = Depends(admin_required)
):
    data = body.model_dump(exclude_none=True)
    data["course_id"] = str(course_id)
    res = supabase.table("chapters").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat chapter")
    return res.data[0]

@router.put("/chapters/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    chapter_id: UUID,
    body: ChapterUpdate,
    current_user: dict = Depends(admin_required)
):
    res = supabase.table("chapters").update(body.model_dump(exclude_none=True)).eq("id", str(chapter_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Chapter tidak ditemukan")
    return res.data[0]

@router.delete("/chapters/{chapter_id}")
async def delete_chapter(
    chapter_id: UUID,
    current_user: dict = Depends(admin_required)
):
    # Hapus semua lesson (subbab) di dalam chapter terlebih dahulu untuk menghindari error foreign key
    supabase.table("lessons").delete().eq("chapter_id", str(chapter_id)).execute()
    
    res = supabase.table("chapters").delete().eq("id", str(chapter_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Chapter tidak ditemukan")
    return {"message": "Chapter berhasil dihapus"}

@router.post("/chapters/reorder")
async def reorder_chapters(
    body: List[dict],
    current_user: dict = Depends(admin_required)
):
    for item in body:
        supabase.table("chapters").update({"sort_order": item["sort_order"]}).eq("id", item["id"]).execute()
    return {"message": "Urutan chapter berhasil diperbarui"}

# --- Lessons ---

@router.post("/chapters/{chapter_id}/lessons", response_model=LessonResponse)
async def create_lesson(
    chapter_id: UUID,
    body: LessonCreate,
    current_user: dict = Depends(admin_required)
):
    data = body.model_dump(exclude_none=True)
    data["chapter_id"] = str(chapter_id)
    res = supabase.table("lessons").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat lesson")
    return res.data[0]

@router.put("/lessons/{lesson_id}", response_model=LessonResponse)
async def update_lesson(
    lesson_id: UUID,
    body: LessonUpdate,
    current_user: dict = Depends(admin_required)
):
    res = supabase.table("lessons").update(body.model_dump(mode="json", exclude_none=True)).eq("id", str(lesson_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Lesson tidak ditemukan")
    return res.data[0]

@router.delete("/lessons/{lesson_id}")
async def delete_lesson(
    lesson_id: UUID,
    current_user: dict = Depends(admin_required)
):
    res = supabase.table("lessons").delete().eq("id", str(lesson_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Lesson tidak ditemukan")
    return {"message": "Lesson berhasil dihapus"}

@router.post("/lessons/reorder")
async def reorder_lessons(
    body: LessonReorder,
    current_user: dict = Depends(admin_required)
):
    for item in body.lessons:
        supabase.table("lessons").update({"sort_order": item.sort_order}).eq("id", str(item.id)).execute()
    return {"message": "Urutan lesson berhasil diperbarui"}

# --- Lesson Content ---

@router.get("/lessons/{lesson_id}/content", response_model=LessonContentResponse)
async def get_lesson_content(
    lesson_id: UUID,
    current_user: dict = Depends(admin_required)
):
    res = supabase.table("lesson_contents").select("*").eq("lesson_id", str(lesson_id)).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Konten lesson tidak ditemukan")
    data = res.data[0]
    # Return body_md if available, fallback to body (legacy BlockNote JSON)
    if data.get("body_md"):
        data["body"] = None
    return data

@router.put("/lessons/{lesson_id}/content", response_model=LessonContentResponse)
async def update_lesson_content(
    lesson_id: UUID,
    body: LessonContentUpdate,
    current_user: dict = Depends(admin_required)
):
    existing = supabase.table("lesson_contents").select("*").eq("lesson_id", str(lesson_id)).execute()

    data = body.model_dump(exclude_none=True)
    data["lesson_id"] = str(lesson_id)
    data["updated_at"] = datetime.now().isoformat()

    # If body_md provided, null out the legacy body to avoid confusion
    if data.get("body_md"):
        data["body"] = None

    if existing.data:
        res = supabase.table("lesson_contents").update(data).eq("lesson_id", str(lesson_id)).execute()
    else:
        res = supabase.table("lesson_contents").insert(data).execute()

    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menyimpan konten lesson")
    return res.data[0]

# --- Upload ---

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(admin_required)
):
    import os
    import uuid
    
    # Read file content
    content = await file.read()
    
    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    
    # Define R2 path
    r2_path = f"materials/attachments/{filename}"
    
    # Upload to R2
    storage_client.upload_file(r2_path, content, file.content_type)
    
    # Return the relative path that the frontend expects
    return {"url": f"/uploads/{r2_path}"}


# --- Markdown Upload & Parse ---

def parse_markdown_structure(md: str) -> dict:
    """Parse markdown text into course structure.

    Expected format:
      # Title
      ## Bab 1: ...
      ### Subbab 1: ...
      content...
      ```gift
      ...
      ```
    """
    lines = md.split("\n")
    course_title = ""
    chapters = []
    current_chapter = None
    current_lesson = None
    in_gift = False
    gift_buffer = []
    content_buffer = []

    for line in lines:
        # Handle ```gift blocks
        if line.strip().startswith("```gift"):
            in_gift = True
            gift_buffer = []
            continue
        if in_gift:
            if line.strip().startswith("```"):
                in_gift = False
                if current_lesson and gift_buffer:
                    current_lesson["gift"] = "\n".join(gift_buffer)
                gift_buffer = []
            else:
                gift_buffer.append(line)
            continue

        if line.startswith("# "):
            course_title = line[2:].strip()
        elif line.startswith("## "):
            # Save previous lesson
            if current_lesson:
                current_lesson["content"] = "\n".join(content_buffer).strip()
                if current_chapter:
                    current_chapter["lessons"].append(current_lesson)
            content_buffer = []
            current_lesson = None

            chapter_title = line[3:].strip()
            current_chapter = {"title": chapter_title, "lessons": []}
            chapters.append(current_chapter)
        elif line.startswith("### "):
            # Save previous lesson
            if current_lesson:
                current_lesson["content"] = "\n".join(content_buffer).strip()
                if current_chapter:
                    current_chapter["lessons"].append(current_lesson)
            content_buffer = []

            lesson_title = line[4:].strip()
            current_lesson = {"title": lesson_title, "content": "", "gift": None}
        else:
            if current_lesson is not None:
                content_buffer.append(line)

    # Save last lesson
    if current_lesson:
        current_lesson["content"] = "\n".join(content_buffer).strip()
        if current_chapter:
            current_chapter["lessons"].append(current_lesson)

    return {"title": course_title, "chapters": chapters}


@router.get("/materi/{course_id}/export")
async def export_materi_markdown(
    course_id: UUID,
    current_user: dict = Depends(admin_required)
):
    """Export course structure to .md file download with R2 public URLs."""
    import uuid as uuid_lib

    course_res = supabase.table("courses").select("*").eq("id", str(course_id)).execute()
    if not course_res.data:
        raise HTTPException(status_code=404, detail="Course tidak ditemukan")
    course = course_res.data[0]

    # Ponytail: uses BACKEND_URL proxy for images. Switch to R2 public domain
    # if the bucket is configured with a custom domain in settings.

    chapters_res = supabase.table("chapters").select("*").eq("course_id", str(course_id)).execute()
    chapters = sorted(chapters_res.data or [], key=lambda x: x.get("sort_order", 0))

    lines = [f"# {course['title']}"]

    if course.get("description"):
        lines.extend(["", course["description"]])

    for ch in chapters:
        lines.extend(["", f"## {ch['title']}"])

        lessons_res = supabase.table("lessons").select("*").eq("chapter_id", ch["id"]).execute()
        lessons = sorted(lessons_res.data or [], key=lambda x: x.get("sort_order", 0))

        for les in lessons:
            lines.extend(["", f"### {les['title']}"])

            if les["content_type"] == "quiz":
                quiz_res = supabase.table("quizzes").select("*").eq("lesson_id", les["id"]).execute()
                if quiz_res.data:
                    quiz = quiz_res.data[0]
                    qs_res = supabase.table("questions").select("*").eq("quiz_id", quiz["id"]).order("sort_order").execute()
                    if qs_res.data:
                        lines.append("```gift")
                        for q in qs_res.data:
                            qtitle = str(q.get("question", "Question"))[:40].strip()
                            lines.append(f"::{qtitle}:: {q['question']}")
                            lines.append("{")
                            for i in range(1, 5):
                                opt = q.get(f"option_{i}")
                                if opt:
                                    prefix = "=" if q.get(f"is_correct_{i}") else "~"
                                    lines.append(f"  {prefix}{opt}")
                            lines.append("}")
                            lines.append("")
                        lines.append("```")
            else:
                content_res = supabase.table("lesson_contents").select("body_md").eq("lesson_id", les["id"]).execute()
                if content_res.data and content_res.data[0].get("body_md"):
                    md = content_res.data[0]["body_md"]
                    # Replace relative /uploads/ paths with public-facing URLs
                    md = md.replace(
                        "](/uploads/",
                        f"]({settings.BACKEND_URL}/uploads/"
                    )
                    lines.append(md)

    md_content = "\n".join(lines)

    from fastapi.responses import Response
    slug = course.get("slug", str(course["id"]))
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{slug}.md"'}
    )


@router.post("/materi/upload")
async def upload_materi_markdown(
    file: UploadFile = File(...),
    current_user: dict = Depends(admin_required)
):
    """Upload a .md file to auto-create course with chapters, lessons, and quizzes."""
    import uuid as uuid_lib

    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="File harus berekstensi .md")

    content_bytes = await file.read()
    try:
        md_content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File harus UTF-8 encoded")

    structure = parse_markdown_structure(md_content)
    if not structure["title"]:
        raise HTTPException(status_code=400, detail="Judul course tidak ditemukan. Gunakan format # Judul")

    import re as re_mod
    slug = re_mod.sub(r'[^\w-]+', '', structure["title"].lower().strip().replace(" ", "-")) or f"course-{uuid_lib.uuid4().hex[:8]}"

    # Create course
    try:
        course_res = supabase.table("courses").insert({
            "title": structure["title"],
            "slug": slug,
            "status": "draft",
        }).execute()
    except Exception as e:
        if "slug" in str(e).lower():
            slug = f"{slug}-{uuid_lib.uuid4().hex[:4]}"
            course_res = supabase.table("courses").insert({
                "title": structure["title"],
                "slug": slug,
                "status": "draft",
            }).execute()
        else:
            raise HTTPException(status_code=400, detail=f"Gagal membuat course: {str(e)}")

    if not course_res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat course")
    course = course_res.data[0]
    course_id = course["id"]

    # Save original markdown file to course_uploads table
    try:
        supabase.table("course_uploads").insert({
            "course_id": str(course_id),
            "filename": file.filename or "uploaded_course.md",
            "original_content": md_content,
            "file_size": len(content_bytes),
        }).execute()
    except Exception as e:
        print(f"WARN: Failed to save original markdown: {e}")
        # Non-fatal — course already created

    created_bab = 0
    created_subbab = 0
    created_quiz = 0

    for ch_idx, chapter in enumerate(structure["chapters"]):
        ch_res = supabase.table("chapters").insert({
            "course_id": str(course_id),
            "title": chapter["title"],
            "sort_order": ch_idx,
        }).execute()
        if not ch_res.data:
            continue
        chapter_id = ch_res.data[0]["id"]
        created_bab += 1

        for les_idx, lesson in enumerate(chapter.get("lessons", [])):
            has_gift = bool(lesson.get("gift"))
            content_type = "rich_text" if not has_gift else "quiz"

            les_res = supabase.table("lessons").insert({
                "chapter_id": str(chapter_id),
                "title": lesson["title"],
                "content_type": content_type,
                "sort_order": les_idx,
            }).execute()
            if not les_res.data:
                continue
            lesson_id = les_res.data[0]["id"]
            created_subbab += 1

            # Save content as markdown
            body_md = lesson.get("content", "")
            supabase.table("lesson_contents").insert({
                "lesson_id": str(lesson_id),
                "body_md": body_md or None,
                "body": [],
            }).execute()

            # Parse GIFT quiz if present
            if has_gift and lesson["gift"].strip():
                questions = parse_gift(lesson["gift"])
                if questions:
                    # Create quiz for this lesson
                    quiz_res = supabase.table("quizzes").insert({
                        "lesson_id": str(lesson_id),
                        "title": f"Quiz: {lesson['title']}",
                        "passing_percentage": 70.0,
                        "total_marks": sum(q.get("marks", 1) for q in questions),
                    }).execute()
                    if quiz_res.data:
                        quiz_id = quiz_res.data[0]["id"]
                        created_quiz += 1

                        # Create questions
                        for q_idx, q in enumerate(questions):
                            supabase.table("questions").insert({
                                "quiz_id": str(quiz_id),
                                "question": q["question"],
                                "type": q["type"],
                                "marks": q.get("marks", 1),
                                "sort_order": q_idx,
                                "multiple": q.get("multiple", False),
                                "option_1": q.get("option_1", ""),
                                "option_2": q.get("option_2", ""),
                                "option_3": q.get("option_3", ""),
                                "option_4": q.get("option_4", ""),
                                "is_correct_1": q.get("is_correct_1", False),
                                "is_correct_2": q.get("is_correct_2", False),
                                "is_correct_3": q.get("is_correct_3", False),
                                "is_correct_4": q.get("is_correct_4", False),
                                "possibility_1": q.get("possibility_1", ""),
                                "possibility_2": q.get("possibility_2", ""),
                                "possibility_3": q.get("possibility_3", ""),
                                "possibility_4": q.get("possibility_4", ""),
                                "explanation_1": q.get("explanation_1", ""),
                                "explanation_2": q.get("explanation_2", ""),
                                "explanation_3": q.get("explanation_3", ""),
                                "explanation_4": q.get("explanation_4", ""),
                            }).execute()

    return {
        "course_id": str(course_id),
        "title": structure["title"],
        "slug": slug,
        "bab_created": created_bab,
        "subbab_created": created_subbab,
        "quiz_created": created_quiz,
    }
