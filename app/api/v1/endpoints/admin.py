from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from app.api.v1.endpoints.auth import get_current_user, require_role
from app.core.auth import get_password_hash
from app.core.postgre import supabase
from datetime import date, datetime
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID
router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])
admin_required = require_role("admin")


# ─── Schemas ────────────────────────────────────────

class PromoCreate(BaseModel):
    code: str
    discount_type: str
    discount_value: float
    applicable_class_ids: Optional[list[str]] = None
    max_usage: Optional[int] = None
    min_amount: Optional[float] = None
    min_children: Optional[int] = 0
    label: Optional[str] = None
    description: Optional[str] = None
    expires_at: Optional[str] = None

class PromoUpdate(PromoCreate):
    is_active: bool = True

class RegistrationStatusUpdate(BaseModel):
    status: str

class RegistrationManualVerificationUpdate(BaseModel):
    is_verified: bool
    class_id: Optional[str] = None
    keterangan: Optional[str] = None

class RegistrationBypassCreate(BaseModel):
    student_id: str
    class_id: str
    keterangan: Optional[str] = None

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    whatsapp_number: Optional[str] = None
    city: Optional[str] = None
    is_active: Optional[bool] = None

class UserPasswordReset(BaseModel):
    new_password: str

class ParentCreate(BaseModel):
    name: str
    email: EmailStr
    whatsapp_number: Optional[str] = None
    city: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = True

class ParentUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    whatsapp_number: Optional[str] = None
    city: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class StudentCreate(BaseModel):
    parent_id: str
    name: Optional[str] = None
    full_name: Optional[str] = None
    username: str
    password: Optional[str] = None
    birth_date: Optional[date] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    school_origin: Optional[str] = None
    level: Optional[str] = None
    status: Optional[str] = "active"
    coding_experience: Optional[str] = None
    interests: Optional[list[str]] = None

class StudentUpdate(BaseModel):
    parent_id: Optional[str] = None
    name: Optional[str] = None
    full_name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    birth_date: Optional[date] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    school_origin: Optional[str] = None
    level: Optional[str] = None
    status: Optional[str] = None
    coding_experience: Optional[str] = None
    interests: Optional[list[str]] = None


# ─── Overview ────────────────────────────────────────

def _sanitize_student(student: dict) -> dict:
    data = dict(student)
    data.pop("password_hash", None)
    return data


def _get_parent_account(parent_id: str) -> dict:
    parent_res = supabase.table("parents").select("id,name,email,role").eq("id", parent_id).execute()
    if not parent_res.data or parent_res.data[0].get("role") != "parent":
        raise HTTPException(status_code=400, detail="Parent tidak valid")
    return parent_res.data[0]


def _student_with_parent(student: dict) -> dict:
    data = _sanitize_student(student)
    parent = None
    if data.get("parent_id"):
        parent_res = supabase.table("parents").select("id,name,email").eq("id", data["parent_id"]).execute()
        parent = parent_res.data[0] if parent_res.data else None
    data["parent"] = parent
    data["parent_name"] = parent.get("name") if parent else None
    data["parent_email"] = parent.get("email") if parent else None
    return data


def _normalize_student_status(status: Optional[str]) -> str:
    value = (status or "active").strip().lower()
    if value in {"inactive", "suspended", "archived"}:
        return "suspended"
    if value in {"preview"}:
        return "preview"
    return "active"


def _normalize_email(value: str) -> str:
    return str(value).strip().lower()


def _create_login_account(
    *,
    name: str,
    email: str,
    password: str,
    role: str,
    whatsapp_number: Optional[str] = None,
    city: Optional[str] = None,
    is_active: Optional[bool] = True,
) -> dict:
    normalized_email = _normalize_email(email)
    if not password or not password.strip():
        raise HTTPException(status_code=400, detail=f"Password {role} wajib diisi")

    existing = supabase.table("parents").select("id").eq("email", normalized_email).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Email sudah terdaftar")

    data = {
        "name": name.strip(),
        "email": normalized_email,
        "whatsapp_number": (whatsapp_number or "").strip(),
        "city": (city or "").strip(),
        "password_hash": get_password_hash(password.strip()),
        "role": role,
        "is_active": True if is_active is None else is_active,
    }
    res = supabase.table("parents").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail=f"Gagal membuat {role}")
    return res.data[0]


class MentorCreate(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = None
    whatsapp_number: Optional[str] = None
    city: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[str] = None
    is_active: Optional[bool] = True

class MentorUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    whatsapp_number: Optional[str] = None
    city: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[str] = None
    is_active: Optional[bool] = None


def _sanitize_account(account: dict) -> dict:
    data = dict(account)
    data.pop("password_hash", None)
    return data


def _mentor_with_profile(account: dict) -> dict:
    data = _sanitize_account(account)
    profile_res = supabase.table("mentors").select("*").eq("parent_id", account["id"]).execute()
    profile = profile_res.data[0] if profile_res.data else None
    data["mentor_profile"] = profile
    data["mentor_id"] = profile.get("id") if profile else None
    data["bio"] = profile.get("bio") if profile else None
    data["expertise"] = profile.get("expertise") if profile else None
    data["is_active"] = profile.get("is_active") if profile else None
    return data


@router.get("/overview")
async def admin_overview(current_user: dict = Depends(admin_required)):
    parents = supabase.table("parents").select("id").eq("role", "parent").execute()
    students = supabase.table("students").select("id").execute()
    regs = supabase.table("registrations").select("*").execute()

    total_parents = len(parents.data) if parents.data else 0
    total_students = len(students.data) if students.data else 0
    total_registrations = len(regs.data) if regs.data else 0
    total_revenue = sum(
        float(r.get("final_amount", 0) or 0) for r in (regs.data or [])
        if r.get("status") in ("active", "completed")
    )

    recent = sorted(
        (r for r in (regs.data or []) if r.get("created_at")),
        key=lambda x: x["created_at"],
        reverse=True
    )[:10]

    return {
        "total_parents": total_parents,
        "total_students": total_students,
        "total_registrations": total_registrations,
        "total_revenue": total_revenue,
        "recent_registrations": recent,
    }


# ─── Parents ────────────────────────────────────────

@router.get("/users")
async def list_users(
    role: Optional[str] = Query(None, description="Filter by role: parent, student, mentor"),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    current_user: dict = Depends(admin_required),
):
    # Fetch all user tables
    parents_res = supabase.table("parents").select("id, name, email, whatsapp_number, city, role, is_active, created_at").execute()
    students_res = supabase.table("students").select("id, name, username, age, gender, birth_date, school_origin, level, status, parent_id, created_at, last_active_at").execute()
    
    users = []
    
    # Process parents/mentors/admins
    for u in (parents_res.data or []):
        if role and u["role"] != role:
            continue
        users.append({
            "id": u["id"],
            "name": u["name"],
            "email": u["email"],
            "role": u["role"],
            "metadata": {
                "whatsapp": u.get("whatsapp_number"),
                "city": u.get("city"),
                "is_active": u.get("is_active"),
            },
            "created_at": u["created_at"]
        })

    # Process students
    for s in (students_res.data or []):
        if role and role != "student":
            continue
        users.append({
            "id": s["id"],
            "name": s["name"],
            "email": s["username"], # Using username as email-like identifier
            "role": "student",
            "metadata": {
                "age": s.get("age"),
                "gender": s.get("gender"),
                "parent_id": s.get("parent_id"),
                "birth_date": s.get("birth_date"),
                "school_origin": s.get("school_origin"),
                "level": s.get("level"),
                "status": s.get("status"),
                "last_active_at": s.get("last_active_at"),
            },
            "created_at": s["created_at"]
        })

    if search:
        q = search.lower()
        users = [
            u for u in users
            if q in u.get("name", "").lower()
            or q in (u.get("email") or "").lower()
            or q in u.get("role", "").lower()
        ]

    total = len(users)
    page = users[offset:offset + limit]
    return {"data": page, "total": total}


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    current_user: dict = Depends(admin_required),
):
    res = supabase.table("parents").select("id,name,email,whatsapp_number,city,role,is_active,created_at").eq("id", user_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    return res.data[0]


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdate,
    current_user: dict = Depends(admin_required),
):
    existing_user = supabase.table("parents").select("id").eq("id", user_id).execute()
    if not existing_user.data:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    update_data = {}
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=400, detail="Nama user wajib diisi")
        update_data["name"] = body.name.strip()
    if body.email is not None:
        email = _normalize_email(body.email)
        existing_email = supabase.table("parents").select("id").eq("email", email).execute()
        if existing_email.data and existing_email.data[0].get("id") != user_id:
            raise HTTPException(status_code=409, detail="Email sudah terdaftar")
        update_data["email"] = email
    if body.whatsapp_number is not None:
        update_data["whatsapp_number"] = body.whatsapp_number
    if body.city is not None:
        update_data["city"] = body.city
    if body.is_active is not None:
        update_data["is_active"] = body.is_active

    if update_data:
        res = supabase.table("parents").update(update_data).eq("id", user_id).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Gagal memperbarui user")

    refreshed = supabase.table("parents").select("id,name,email,whatsapp_number,city,role,is_active,created_at").eq("id", user_id).execute()
    return refreshed.data[0]


@router.put("/users/{user_id}/password")
async def reset_user_password(
    user_id: str,
    body: UserPasswordReset,
    current_user: dict = Depends(admin_required),
):
    if not body.new_password or not body.new_password.strip():
        raise HTTPException(status_code=400, detail="Password baru wajib diisi")

    existing_user = supabase.table("parents").select("id").eq("id", user_id).execute()
    if not existing_user.data:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    res = supabase.table("parents").update({
        "password_hash": get_password_hash(body.new_password),
    }).eq("id", user_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal mereset password")

    refreshed = supabase.table("parents").select("id,name,email,whatsapp_number,city,role,created_at").eq("id", user_id).execute()
    return refreshed.data[0]


@router.get("/parents")
async def list_parents(
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(admin_required),
):
    all_data = supabase.table("parents").select("*").eq("role", "parent").execute()
    if not all_data.data:
        return {"data": [], "total": 0}

    # Filter out admin accounts — only show parents
    parents = all_data.data

    if search:
        q = search.lower()
        parents = [
            p for p in parents
            if q in p.get("name", "").lower()
            or q in p.get("email", "").lower()
            or q in p.get("whatsapp_number", "")
        ]

    total = len(parents)
    page = parents[offset:offset + limit]
    return {"data": page, "total": total}


@router.post("/parents", status_code=201)
async def create_parent(
    body: ParentCreate,
    current_user: dict = Depends(admin_required),
):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Nama parent wajib diisi")
    if not body.password or not body.password.strip():
        raise HTTPException(status_code=400, detail="Password parent wajib diisi")
    return _create_login_account(
        name=body.name,
        email=str(body.email),
        password=body.password,
        role="parent",
        whatsapp_number=body.whatsapp_number,
        city=body.city,
        is_active=body.is_active,
    )


@router.get("/parents/{parent_id}")
async def get_parent_detail(
    parent_id: str,
    current_user: dict = Depends(admin_required),
):
    # Get parent info
    parent_res = supabase.table("parents").select("*").eq("id", parent_id).execute()
    if not parent_res.data:
        raise HTTPException(status_code=404, detail="Parent tidak ditemukan")

    parent = parent_res.data[0]
    if parent.get("role") != "parent":
        raise HTTPException(status_code=404, detail="Parent tidak ditemukan")

    # Get children
    students_res = supabase.table("students").select("*").eq("parent_id", parent_id).execute()
    children = students_res.data or []

    # Get registrations for each child
    for child in children:
        regs_res = supabase.table("registrations").select("*").eq("student_id", child["id"]).execute()
        child["registrations"] = regs_res.data or []

    return {
        "parent": parent,
        "children": children,
    }


# ─── Students ───────────────────────────────────────

@router.put("/parents/{parent_id}")
async def update_parent(
    parent_id: str,
    body: ParentUpdate,
    current_user: dict = Depends(admin_required),
):
    parent_res = supabase.table("parents").select("*").eq("id", parent_id).execute()
    if not parent_res.data:
        raise HTTPException(status_code=404, detail="Parent tidak ditemukan")

    parent = parent_res.data[0]
    if parent.get("role") != "parent":
        raise HTTPException(status_code=404, detail="Parent tidak ditemukan")

    update_data = {}
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=400, detail="Nama parent wajib diisi")
        update_data["name"] = body.name.strip()
    if body.email is not None:
        email = _normalize_email(body.email)
        existing = supabase.table("parents").select("id").eq("email", email).execute()
        if existing.data and existing.data[0].get("id") != parent_id:
            raise HTTPException(status_code=409, detail="Email sudah terdaftar")
        update_data["email"] = email
    if body.whatsapp_number is not None:
        update_data["whatsapp_number"] = body.whatsapp_number
    if body.city is not None:
        update_data["city"] = body.city
    if body.password is not None and body.password.strip():
        update_data["password_hash"] = get_password_hash(body.password)
    if body.is_active is not None:
        update_data["is_active"] = body.is_active

    if not update_data:
        return parent

    res = supabase.table("parents").update(update_data).eq("id", parent_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui parent")

    return res.data[0]


@router.delete("/parents/{parent_id}")
async def delete_parent(
    parent_id: str,
    current_user: dict = Depends(admin_required),
):
    parent_res = supabase.table("parents").select("*").eq("id", parent_id).execute()
    if not parent_res.data:
        raise HTTPException(status_code=404, detail="Parent tidak ditemukan")

    parent = parent_res.data[0]
    if parent.get("role") != "parent":
        raise HTTPException(status_code=404, detail="Parent tidak ditemukan")

    students_res = supabase.table("students").select("id").eq("parent_id", parent_id).execute()
    if students_res.data:
        raise HTTPException(status_code=400, detail="Parent masih memiliki data siswa, hapus atau pindahkan siswa terlebih dahulu")

    supabase.table("parents").delete().eq("id", parent_id).execute()
    return {"message": "Parent berhasil dihapus"}


@router.get("/mentors")
async def list_mentors(
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    current_user: dict = Depends(admin_required),
):
    all_data = supabase.table("parents").select("id,name,email,whatsapp_number,city,role,created_at").eq("role", "mentor").execute()
    if not all_data.data:
        return {"data": [], "total": 0}

    profiles_by_parent_id = {}
    try:
        profile_res = supabase.table("mentors").select("*").execute()
        profiles_by_parent_id = {
            profile.get("parent_id"): profile
            for profile in (profile_res.data or [])
            if profile.get("parent_id")
        }
    except Exception:
        profiles_by_parent_id = {}

    mentors = []
    for mentor in all_data.data:
        profile = profiles_by_parent_id.get(mentor.get("id"), {})
        mentors.append({
            **mentor,
            "mentor_profile": profile or None,
            "bio": profile.get("bio"),
            "expertise": profile.get("expertise"),
            "is_active": profile.get("is_active"),
        })

    if search:
        q = search.lower()
        mentors = [
            m for m in mentors
            if q in m.get("name", "").lower()
            or q in m.get("email", "").lower()
            or q in m.get("whatsapp_number", "")
            or q in (m.get("expertise") or "").lower()
            or q in (m.get("bio") or "").lower()
        ]

    total = len(mentors)
    page = mentors[offset:offset + limit]
    return {"data": page, "total": total}


@router.post("/mentors", status_code=201)
async def create_mentor(
    body: MentorCreate,
    current_user: dict = Depends(admin_required),
):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Nama mentor wajib diisi")
    if not body.password or not body.password.strip():
        raise HTTPException(status_code=400, detail="Password mentor wajib diisi")
    account = _create_login_account(
        name=body.name,
        email=str(body.email),
        password=body.password,
        role="mentor",
        whatsapp_number=body.whatsapp_number,
        city=body.city,
        is_active=body.is_active,
    )
    profile_data = {
        "parent_id": account["id"],
        "bio": body.bio or "",
        "expertise": body.expertise or "",
        "is_active": True if body.is_active is None else body.is_active,
    }
    try:
        profile_res = supabase.table("mentors").insert(profile_data).execute()
    except Exception:
        supabase.table("parents").delete().eq("id", account["id"]).execute()
        raise HTTPException(status_code=500, detail="Gagal membuat profile mentor")

    if not profile_res.data:
        supabase.table("parents").delete().eq("id", account["id"]).execute()
        raise HTTPException(status_code=500, detail="Gagal membuat profile mentor")

    return _mentor_with_profile(account)


@router.get("/mentors/{mentor_id}")
async def get_mentor_detail(
    mentor_id: str,
    current_user: dict = Depends(admin_required),
):
    account_res = supabase.table("parents").select("*").eq("id", mentor_id).execute()
    if not account_res.data or account_res.data[0].get("role") != "mentor":
        raise HTTPException(status_code=404, detail="Mentor tidak ditemukan")

    return _mentor_with_profile(account_res.data[0])


@router.put("/mentors/{mentor_id}")
async def update_mentor(
    mentor_id: str,
    body: MentorUpdate,
    current_user: dict = Depends(admin_required),
):
    account_res = supabase.table("parents").select("*").eq("id", mentor_id).execute()
    if not account_res.data or account_res.data[0].get("role") != "mentor":
        raise HTTPException(status_code=404, detail="Mentor tidak ditemukan")

    account_update = {}
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=400, detail="Nama mentor wajib diisi")
        account_update["name"] = body.name.strip()
    if body.email is not None:
        email = _normalize_email(body.email)
        existing = supabase.table("parents").select("id").eq("email", email).execute()
        if existing.data and existing.data[0].get("id") != mentor_id:
            raise HTTPException(status_code=409, detail="Email sudah terdaftar")
        account_update["email"] = email
    if body.whatsapp_number is not None:
        account_update["whatsapp_number"] = body.whatsapp_number
    if body.city is not None:
        account_update["city"] = body.city
    if body.password is not None and body.password.strip():
        account_update["password_hash"] = get_password_hash(body.password)

    if account_update:
        account_res = supabase.table("parents").update(account_update).eq("id", mentor_id).execute()
        if not account_res.data:
            raise HTTPException(status_code=500, detail="Gagal memperbarui akun mentor")

    profile_update = {}
    if body.bio is not None:
        profile_update["bio"] = body.bio
    if body.expertise is not None:
        profile_update["expertise"] = body.expertise
    if body.is_active is not None:
        profile_update["is_active"] = body.is_active

    profile_res = supabase.table("mentors").select("id").eq("parent_id", mentor_id).execute()
    if profile_update:
        if profile_res.data:
            updated_profile = supabase.table("mentors").update(profile_update).eq("parent_id", mentor_id).execute()
            if not updated_profile.data:
                raise HTTPException(status_code=500, detail="Gagal memperbarui profile mentor")
        else:
            profile_data = {
                "parent_id": mentor_id,
                "bio": profile_update.get("bio", ""),
                "expertise": profile_update.get("expertise", ""),
                "is_active": profile_update.get("is_active", True),
            }
            created_profile = supabase.table("mentors").insert(profile_data).execute()
            if not created_profile.data:
                raise HTTPException(status_code=500, detail="Gagal membuat profile mentor")

    refreshed = supabase.table("parents").select("*").eq("id", mentor_id).execute()
    return _mentor_with_profile(refreshed.data[0])


@router.delete("/mentors/{mentor_id}")
async def delete_mentor(
    mentor_id: str,
    current_user: dict = Depends(admin_required),
):
    account_res = supabase.table("parents").select("*").eq("id", mentor_id).execute()
    if not account_res.data or account_res.data[0].get("role") != "mentor":
        raise HTTPException(status_code=404, detail="Mentor tidak ditemukan")

    profile_res = supabase.table("mentors").select("id").eq("parent_id", mentor_id).execute()
    profile = profile_res.data[0] if profile_res.data else None
    if profile:
        linked_tables = [
            ("schedules", "jadwal"),
            ("session_reports", "session report"),
            ("final_reports", "final report"),
        ]
        for table_name, label in linked_tables:
            try:
                linked = supabase.table(table_name).select("id").eq("mentor_id", profile["id"]).execute()
            except Exception:
                continue
            if linked.data:
                raise HTTPException(status_code=400, detail=f"Mentor masih memiliki data {label}, tidak bisa dihapus")

        supabase.table("mentors").delete().eq("parent_id", mentor_id).execute()

    supabase.table("parents").delete().eq("id", mentor_id).execute()
    return {"message": "Mentor berhasil dihapus"}


@router.get("/students")
async def list_students(
    search: Optional[str] = Query(None),
    parent_id: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
    current_user: dict = Depends(admin_required),
):
    if parent_id:
        all_data = supabase.table("students").select("*").eq("parent_id", parent_id).execute()
    else:
        all_data = supabase.table("students").select("*").execute()

    if not all_data.data:
        return {"data": [], "total": 0}

    students = [_student_with_parent(student) for student in all_data.data]
    if search:
        q = search.lower()
        students = [
            s for s in students
            if q in s.get("name", "").lower()
            or q in s.get("username", "").lower()
            or q in (s.get("parent_name") or "").lower()
            or q in (s.get("parent_email") or "").lower()
        ]

    total = len(students)
    page = students[offset:offset + limit]
    return {"data": page, "total": total}


@router.post("/students", status_code=201)
async def create_student(
    body: StudentCreate,
    current_user: dict = Depends(admin_required),
):
    _get_parent_account(body.parent_id)

    name = (body.name or body.full_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nama student wajib diisi")
    if not body.username.strip():
        raise HTTPException(status_code=400, detail="Username student wajib diisi")
    if not body.password or not body.password.strip():
        raise HTTPException(status_code=400, detail="Password student wajib diisi")

    username = body.username.strip()
    existing = supabase.table("students").select("id").eq("username", username).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Username sudah terdaftar")

    data = {
        "parent_id": body.parent_id,
        "name": name,
        "username": username,
        "password_hash": get_password_hash(body.password),
        "birth_date": body.birth_date.isoformat() if body.birth_date else None,
        "age": body.age,
        "gender": body.gender.strip() if body.gender and body.gender.strip() else None,
        "school_origin": body.school_origin or "",
        "level": body.level or "",
        "status": _normalize_student_status(body.status),
        "coding_experience": body.coding_experience or "",
        "interests": body.interests or [],
    }
    res = supabase.table("students").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat student")

    return _student_with_parent(res.data[0])


@router.get("/students/{student_id}")
async def get_student_detail(
    student_id: str,
    current_user: dict = Depends(admin_required),
):
    student_res = supabase.table("students").select("*").eq("id", student_id).execute()
    if not student_res.data:
        raise HTTPException(status_code=404, detail="Student tidak ditemukan")

    return _student_with_parent(student_res.data[0])


@router.put("/students/{student_id}")
async def update_student(
    student_id: str,
    body: StudentUpdate,
    current_user: dict = Depends(admin_required),
):
    student_res = supabase.table("students").select("*").eq("id", student_id).execute()
    if not student_res.data:
        raise HTTPException(status_code=404, detail="Student tidak ditemukan")

    update_data = {}
    if body.parent_id is not None:
        _get_parent_account(body.parent_id)
        update_data["parent_id"] = body.parent_id
    if body.name is not None or body.full_name is not None:
        name = (body.name if body.name is not None else body.full_name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Nama student wajib diisi")
        update_data["name"] = name
    if body.username is not None:
        username = body.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username student wajib diisi")
        existing = supabase.table("students").select("id").eq("username", username).execute()
        if existing.data and existing.data[0].get("id") != student_id:
            raise HTTPException(status_code=409, detail="Username sudah terdaftar")
        update_data["username"] = username
    if body.password is not None and body.password.strip():
        update_data["password_hash"] = get_password_hash(body.password)
    if body.birth_date is not None:
        update_data["birth_date"] = body.birth_date.isoformat()
    if body.age is not None:
        update_data["age"] = body.age
    if body.gender is not None:
        update_data["gender"] = body.gender.strip() if body.gender.strip() else None
    if body.school_origin is not None:
        update_data["school_origin"] = body.school_origin
    if body.level is not None:
        update_data["level"] = body.level
    if body.status is not None:
        update_data["status"] = _normalize_student_status(body.status)
    if body.coding_experience is not None:
        update_data["coding_experience"] = body.coding_experience
    if body.interests is not None:
        update_data["interests"] = body.interests

    if not update_data:
        return _student_with_parent(student_res.data[0])

    res = supabase.table("students").update(update_data).eq("id", student_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui student")

    return _student_with_parent(res.data[0])


@router.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    force: bool = Query(False, description="Force delete even if linked data exists"),
    current_user: dict = Depends(admin_required),
):
    student_res = supabase.table("students").select("id").eq("id", student_id).execute()
    if not student_res.data:
        raise HTTPException(status_code=404, detail="Student tidak ditemukan")

    if not force:
        linked_tables = [
            ("registrations", "registrasi"),
            ("enrollments", "enrollment"),
            ("lesson_progress", "progress lesson"),
            ("quiz_submissions", "quiz submission"),
            ("attendances", "attendance"),
            ("session_reports", "session report"),
            ("final_reports", "final report"),
            ("certificates", "certificate"),
        ]
        for table_name, label in linked_tables:
            try:
                linked = supabase.table(table_name).select("id").eq("student_id", student_id).execute()
            except Exception:
                continue
            if linked.data:
                raise HTTPException(status_code=400, detail=f"Student masih memiliki data {label}, tidak bisa dihapus")
    else:
        # Force mode: cascade delete all linked records
        cascade_tables = [
            "certificates", "final_reports", "session_reports",
            "attendances", "quiz_submissions", "lesson_progress",
            "enrollments", "registrations",
        ]
        for table_name in cascade_tables:
            try:
                supabase.table(table_name).delete().eq("student_id", student_id).execute()
            except Exception:
                pass

    supabase.table("students").delete().eq("id", student_id).execute()
    return {"message": "Student berhasil dihapus"}


# ─── Registrations ──────────────────────────────────

@router.get("/registrations")
async def list_registrations(
    status: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(admin_required),
):
    if status:
        all_data = supabase.table("registrations").select("*").eq("status", status).execute()
    else:
        all_data = supabase.table("registrations").select("*").execute()

    data = all_data.data or []
    for reg in data:
        student_name = None
        parent_email = None
        class_name = None
        if reg.get("student_id"):
            student_res = supabase.table("students").select("*").eq("id", reg["student_id"]).execute()
            if student_res.data:
                student = student_res.data[0]
                student_name = student.get("name")
                if student.get("parent_id"):
                    parent_res = supabase.table("parents").select("*").eq("id", student["parent_id"]).execute()
                    if parent_res.data:
                        parent_email = parent_res.data[0].get("email")
        if reg.get("class_id"):
            class_res = supabase.table("classes").select("*").eq("id", reg["class_id"]).execute()
            if class_res.data:
                class_name = class_res.data[0].get("display_name") or class_res.data[0].get("name")
        reg["student_name"] = student_name
        reg["parent_email"] = parent_email
        reg["class_name"] = class_name
        reg["midtrans_status"] = reg.get("midtrans_transaction_status") or reg.get("status")
    total = len(data)
    page = data[offset:offset + limit]
    return {"data": page, "total": total}


@router.put("/registrations/{reg_id}/status")
async def update_registration_status(
    reg_id: str,
    body: RegistrationStatusUpdate,
    current_user: dict = Depends(admin_required),
):
    res = supabase.table("registrations").select("*").eq("id", reg_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registrasi tidak ditemukan")
    
    reg = res.data[0]
    old_status = reg.get("status")
    
    # Update registration status
    up_res = supabase.table("registrations").update({
        "status": body.status,
    }).eq("id", reg_id).execute()
    
    if not up_res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui status registrasi")

    # If changed to paid, automatically create enrollment
    if body.status in ("paid", "active", "completed") and old_status != body.status:
        student_id = reg.get("student_id")
        class_id = reg.get("class_id")
        
        if student_id and class_id:
            # 1. Get all course_ids for this batch
            cp_res = supabase.table("class_programs").select("course_id").eq("class_id", class_id).execute()
            course_ids = [row["course_id"] for row in cp_res.data] if cp_res.data else []
            
            # Fallback to legacy single course_id
            if not course_ids:
                class_res = supabase.table("classes").select("course_id").eq("id", class_id).execute()
                if class_res.data and class_res.data[0].get("course_id"):
                    course_ids = [class_res.data[0]["course_id"]]
            
            # 2. Get all course_ids from all linked programs
            all_course_ids = set()
            if course_ids:
                pc_res = supabase.table("program_courses").select("course_id").in_("course_id", course_ids).execute()
                if pc_res.data:
                    for row in pc_res.data:
                        all_course_ids.add(row["course_id"])
            
            # 3. Add any directly linked course_ids (legacy or class_materi)
            cc_res = supabase.table("class_materi").select("course_id").eq("class_id", class_id).execute()
            if cc_res.data:
                for row in cc_res.data:
                    all_course_ids.add(row["course_id"])
                    
            # 4. Perform enrollments
            for c_id in all_course_ids:
                # Check if enrollment already exists
                existing = supabase.table("enrollments").select("id").eq("student_id", student_id).eq("course_id", c_id).eq("class_id", class_id).execute()
                if not existing.data:
                    supabase.table("enrollments").insert({
                        "student_id": student_id,
                        "course_id": c_id,
                        "class_id": class_id,
                        "status": "active"
                    }).execute()
            
            # 5. Increment filled_quota on class/batch & Recalculate status based on dynamic quota
            # Crucial: Only increment if the status being set is 'active' or if it's a new successful registration
            if body.status in ["paid", "active"]:
                try:
                    # Calculate total_max dynamically
                    total_max = 0
                    if course_ids:
                        p_res = supabase.table("programs").select("max_quota").in_("id", course_ids).eq("is_active", True).execute()
                        if p_res.data:
                            total_max = sum(p.get("max_quota", 0) for p in p_res.data)
                    
                    class_res = supabase.table("classes").select("max_quota, filled_quota").eq("id", class_id).execute()
                    if class_res.data:
                        cls = class_res.data[0]
                        if total_max == 0:
                            total_max = cls.get("max_quota") or 0
                        
                        filled_q = (cls.get("filled_quota") or 0) + 1
                        
                        update_payload = {"filled_quota": filled_q}
                        if total_max > 0:
                            if filled_q >= total_max:
                                update_payload["status"] = "full"
                            elif filled_q >= int(total_max * 0.8):
                                update_payload["status"] = "almost_full"
                            else:
                                update_payload["status"] = "open"
                            
                        supabase.table("classes").update(update_payload).eq("id", class_id).execute()
                except Exception as ex:
                    print(f"Failed to update class quota: {ex}")

    return {"message": "Status berhasil diperbarui", "status": body.status}


@router.put("/registrations/{reg_id}/manual-verification")
async def update_registration_manual_verification(
    reg_id: str,
    body: RegistrationManualVerificationUpdate,
    current_user: dict = Depends(admin_required),
):
    res = supabase.table("registrations").select("*").eq("id", reg_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registrasi tidak ditemukan")

    # Use selected class_id if provided, otherwise fallback to class_id from registration
    class_id = body.class_id if body.class_id else res.data[0].get("class_id")

    data = {
        "manual_verified": body.is_verified,
        "verified_by": str(current_user["id"]) if body.is_verified else None,
        "verified_at": datetime.now().isoformat() if body.is_verified else None,
        "class_id": class_id,
        "keterangan": body.keterangan if body.keterangan else (res.data[0].get("keterangan") or ("Bypass Admin (Belum Bayar)" if body.is_verified else None))
    }
    if body.is_verified and res.data[0].get("status") == "pending":
        data["status"] = "active"

    up_res = supabase.table("registrations").update(data).eq("id", reg_id).execute()
    if not up_res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui verifikasi manual")

    reg = up_res.data[0]
    if body.is_verified:
        student_id = reg.get("student_id")
        if student_id and class_id:
            # Get course_ids from class_materi
            cc_res = supabase.table("class_materi").select("course_id").eq("class_id", class_id).execute()
            course_ids = [row["course_id"] for row in cc_res.data] if cc_res.data else []
            
            # Fallback to legacy class.course_id
            if not course_ids:
                class_res = supabase.table("classes").select("course_id").eq("id", class_id).execute()
                if class_res.data and class_res.data[0].get("course_id"):
                    course_ids = [class_res.data[0]["course_id"]]
                    
            for c_id in course_ids:
                existing = supabase.table("enrollments").select("id").eq("student_id", student_id).eq("course_id", c_id).execute()
                if not existing.data:
                    supabase.table("enrollments").insert({
                        "student_id": student_id,
                        "course_id": c_id,
                        "class_id": class_id,
                        "status": "active",
                    }).execute()

    return {"message": "Verifikasi manual berhasil diperbarui", "data": up_res.data[0]}


@router.post("/registrations/bypass", status_code=201)
async def create_bypass_registration(
    body: RegistrationBypassCreate,
    current_user: dict = Depends(admin_required),
):
    # Verify student exists
    st_res = supabase.table("students").select("id").eq("id", body.student_id).execute()
    if not st_res.data:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")

    # Verify class exists and get base_price
    cl_res = supabase.table("classes").select("id, base_price").eq("id", body.class_id).execute()
    if not cl_res.data:
        raise HTTPException(status_code=404, detail="Kelas/Batch tidak ditemukan")
    cls_data = cl_res.data[0]
    base_price = float(cls_data.get("base_price", 0))

    # Insert registration
    reg_data = {
        "student_id": body.student_id,
        "class_id": body.class_id,
        "status": "active",
        "manual_verified": True,
        "verified_by": str(current_user["id"]),
        "verified_at": datetime.now().isoformat(),
        "amount": base_price,
        "final_amount": base_price,
        "keterangan": body.keterangan or "Bypass Admin (Belum Bayar)",
        "payment_method": "Bypass Admin (Belum Bayar)"
    }
    
    reg_res = supabase.table("registrations").insert(reg_data).execute()
    if not reg_res.data:
        raise HTTPException(status_code=500, detail="Gagal menyimpan pendaftaran bypass")

    # Enroll student in courses linked to class
    cc_res = supabase.table("class_materi").select("course_id").eq("class_id", body.class_id).execute()
    course_ids = [row["course_id"] for row in cc_res.data] if cc_res.data else []
    
    if not course_ids:
        class_res = supabase.table("classes").select("course_id").eq("id", body.class_id).execute()
        if class_res.data and class_res.data[0].get("course_id"):
            course_ids = [class_res.data[0]["course_id"]]

    for c_id in course_ids:
        existing = supabase.table("enrollments").select("id").eq("student_id", body.student_id).eq("course_id", c_id).execute()
        if not existing.data:
            supabase.table("enrollments").insert({
                "student_id": body.student_id,
                "course_id": c_id,
                "class_id": body.class_id,
                "status": "active",
            }).execute()

    return {"message": "Pendaftaran bypass berhasil dibuat", "data": reg_res.data[0]}



# ─── Promo Codes ────────────────────────────────────
@router.get("/promo")
async def list_promo(current_user: dict = Depends(admin_required)):
    res = supabase.table("promo_codes").select("*").execute()
    return {"data": res.data or []}


@router.post("/promo", status_code=201)
async def create_promo(
    body: PromoCreate,
    current_user: dict = Depends(admin_required),
):
    if body.discount_value < 0:
        raise HTTPException(status_code=400, detail="Nilai diskon tidak boleh negatif")
    if body.discount_type == "percentage" and body.discount_value > 100:
        raise HTTPException(status_code=400, detail="Nilai diskon persentase tidak boleh melebihi 100%")

    data = body.model_dump(exclude_none=True)
    res = supabase.table("promo_codes").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat promo")
    return res.data[0]


@router.put("/promo/{promo_id}")
async def update_promo(
    promo_id: str,
    body: PromoUpdate,
    current_user: dict = Depends(admin_required),
):
    existing = supabase.table("promo_codes").select("id").eq("id", promo_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Promo tidak ditemukan")

    if body.discount_value < 0:
        raise HTTPException(status_code=400, detail="Nilai diskon tidak boleh negatif")
    if body.discount_type == "percentage" and body.discount_value > 100:
        raise HTTPException(status_code=400, detail="Nilai diskon persentase tidak boleh melebihi 100%")

    data = body.model_dump(exclude_none=True)
    supabase.table("promo_codes").update(data).eq("id", promo_id).execute()
    return {"message": "Promo berhasil diperbarui"}


@router.delete("/promo/{promo_id}")
async def delete_promo(
    promo_id: str,
    current_user: dict = Depends(admin_required),
):
    existing = supabase.table("promo_codes").select("id").eq("id", promo_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Promo tidak ditemukan")

    supabase.table("promo_codes").delete().eq("id", promo_id).execute()
    return {"message": "Promo berhasil dihapus"}


# ─── Admin Portal Expansion: Extra Schemas & Endpoints ────────────────

from datetime import datetime

class AdminCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    whatsapp_number: Optional[str] = None
    is_active: Optional[bool] = True

class AdminUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    whatsapp_number: Optional[str] = None
    is_active: Optional[bool] = None

class BatchCreate(BaseModel):
    name: str
    display_name: str
    subtitle: Optional[str] = None
    base_price: float
    category: Optional[str] = None
    items: Optional[list[str]] = None
    is_active: Optional[bool] = True
    course_id: Optional[str] = None
    course_ids: Optional[list[str]] = None
    course_id: Optional[str] = None
    course_ids: Optional[list[str]] = None
    max_quota: Optional[int] = None
    filled_quota: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    dashboard_layout: Optional[dict] = None
    image_url: Optional[str] = None

class BatchUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    subtitle: Optional[str] = None
    base_price: Optional[float] = None
    category: Optional[str] = None
    items: Optional[list[str]] = None
    is_active: Optional[bool] = None
    course_id: Optional[str] = None
    course_ids: Optional[list[str]] = None
    course_id: Optional[str] = None
    course_ids: Optional[list[str]] = None
    max_quota: Optional[int] = None
    filled_quota: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    dashboard_layout: Optional[dict] = None
    image_url: Optional[str] = None

class ProgramCreate(BaseModel):
    title: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = True
    max_quota: Optional[int] = 0
    course_ids: Optional[list[str]] = None
    batch_id: Optional[str] = None
    mentor_ids: Optional[list[str]] = None

class ProgramUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    max_quota: Optional[int] = None
    course_ids: Optional[list[str]] = None
    batch_id: Optional[str] = None
    mentor_ids: Optional[list[str]] = None

class CourseMentorAssign(BaseModel):
    mentor_ids: list[str]

class ProgramCourseReorder(BaseModel):
    course_ids: list[str]  # in new order

class StudentToggleEnrollment(BaseModel):
    student_id: str
    enrolled: bool  # True = add/enroll, False = remove/waitlist

class ProgramStudentStatus(BaseModel):
    student_id: str
    student_name: str
    student_age: Optional[int] = None
    student_gender: Optional[str] = None
    parent_name: Optional[str] = None
    parent_email: Optional[str] = None
    enrolled: bool  # currently enrolled in this program?

class EnrollmentCreate(BaseModel):
    student_id: str
    course_id: str
    class_id: Optional[str] = None
    status: Optional[str] = "active"

class EnrollmentUpdate(BaseModel):
    status: str

class CertificateCreate(BaseModel):
    enrollment_id: str
    student_id: str
    certificate_number: str
    title: str
    file_url: Optional[str] = None
    status: Optional[str] = "issued"

class CertificateUpdate(BaseModel):
    title: Optional[str] = None
    file_url: Optional[str] = None
    status: Optional[str] = None

class ScheduleCreate(BaseModel):
    enrollment_id: Optional[str] = None
    course_id: Optional[str] = None
    mentor_id: str
    title: str
    class_type: str  # online, offline, hybrid
    start_time: str
    end_time: str
    location: Optional[str] = None
    generate_zoom: Optional[bool] = False

class ScheduleUpdate(BaseModel):
    enrollment_id: Optional[str] = None
    course_id: Optional[str] = None
    mentor_id: Optional[str] = None
    title: Optional[str] = None
    class_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    zoom_join_url: Optional[str] = None
    status: Optional[str] = None


# ─── Admin User CRUD ────────────────────────────────

@router.post("/admins", status_code=201)
async def create_admin(body: AdminCreate, current_user: dict = Depends(admin_required)):
    account = _create_login_account(
        name=body.name,
        email=str(body.email),
        password=body.password,
        role="admin",
        whatsapp_number=body.whatsapp_number,
        is_active=body.is_active,
    )
    return _sanitize_account(account)

@router.put("/admins/{admin_id}")
async def update_admin(admin_id: str, body: AdminUpdate, current_user: dict = Depends(admin_required)):
    existing = supabase.table("parents").select("*").eq("id", admin_id).execute()
    if not existing.data or existing.data[0].get("role") != "admin":
        raise HTTPException(status_code=404, detail="Admin tidak ditemukan")
        
    data = {}
    if body.name is not None:
        data["name"] = body.name
    if body.email is not None:
        email = _normalize_email(body.email)
        existing_email = supabase.table("parents").select("id").eq("email", email).execute()
        if existing_email.data and existing_email.data[0]["id"] != admin_id:
            raise HTTPException(status_code=409, detail="Email sudah terdaftar")
        data["email"] = email
    if body.password is not None and body.password.strip():
        data["password_hash"] = get_password_hash(body.password)
    if body.whatsapp_number is not None:
        data["whatsapp_number"] = body.whatsapp_number
    if body.is_active is not None:
        data["is_active"] = body.is_active
        
    if not data:
        return _sanitize_account(existing.data[0])
        
    res = supabase.table("parents").update(data).eq("id", admin_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui admin")
    return _sanitize_account(res.data[0])

@router.delete("/admins/{admin_id}")
async def delete_admin(admin_id: str, current_user: dict = Depends(admin_required)):
    existing = supabase.table("parents").select("id, role").eq("id", admin_id).execute()
    if not existing.data or existing.data[0].get("role") != "admin":
        raise HTTPException(status_code=404, detail="Admin tidak ditemukan")
        
    supabase.table("parents").delete().eq("id", admin_id).execute()
    return {"message": "Admin berhasil dihapus"}


# ─── Programs CRUD ──────────────────────────────────

@router.get("/programs")
async def list_programs(current_user: dict = Depends(admin_required)):
    res = supabase.table("programs").select("*").order("created_at", desc=True).execute()
    programs = res.data or []
    for p in programs:
        prog_id = p["id"]
        # Fetch bundled course_ids from program_courses
        pc_res = supabase.table("program_courses").select("course_id").eq("program_id", prog_id).order("sort_order").execute()
        p["course_ids"] = [row["course_id"] for row in pc_res.data] if pc_res.data else []

        # Fetch mentor_ids from course_mentors (return parent_id for frontend consistency)
        cm_res = supabase.table("course_mentors").select("mentor_id").eq("program_id", prog_id).execute()
        mentor_ids_raw = [row["mentor_id"] for row in cm_res.data] if cm_res.data else []
        p["mentor_ids"] = []
        if mentor_ids_raw:
            m_res = supabase.table("mentors").select("parent_id").in_("id", mentor_ids_raw).execute()
            p["mentor_ids"] = [row["parent_id"] for row in m_res.data] if m_res.data else []
        
        # Fetch associated batch via class_programs
        batch_res = supabase.table("class_programs").select("class_id").eq("program_id", prog_id).limit(1).execute()
        p["batch_id"] = batch_res.data[0]["class_id"] if batch_res.data else None
        
        # Populate course_titles (for Materi column)
        course_titles = []
        for c_id in p["course_ids"]:
            c_res = supabase.table("courses").select("title").eq("id", c_id).execute()
            if c_res.data:
                course_titles.append(c_res.data[0]["title"])
        p["course_titles"] = course_titles
        
        batch_name = None
        enrolled_count = 0
        if p["batch_id"]:
            # Fetch batch display_name
            cls_res = supabase.table("classes").select("id, display_name").eq("id", p["batch_id"]).execute()
            if cls_res.data:
                cls = cls_res.data[0]
                batch_name = cls["display_name"]
                # Count unique active enrolled students for THIS program's courses in this batch
                if p["course_ids"]:
                    enr_res = supabase.table("enrollments").select("student_id") \
                        .in_("course_id", p["course_ids"]) \
                        .eq("class_id", p["batch_id"]) \
                        .eq("status", "active") \
                        .execute()
                    enrolled_set = set(r["student_id"] for r in (enr_res.data or []))
                    enrolled_count = len(enrolled_set)
                p["linked_classes"] = [{
                    "id": cls["id"],
                    "display_name": cls["display_name"],
                    "enrolled_count": enrolled_count
                }]
            else:
                p["linked_classes"] = []
        else:
            p["linked_classes"] = []
        p["enrolled_count"] = enrolled_count
    return {"data": programs}

@router.post("/programs", status_code=201)
async def create_program(body: ProgramCreate, current_user: dict = Depends(admin_required)):
    data = body.model_dump(exclude_none=True)
    course_ids = data.pop("course_ids", None)
    batch_id = data.pop("batch_id", None)
    mentor_ids = data.pop("mentor_ids", None)
    
    res = supabase.table("programs").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat program/course")
        
    created_program = res.data[0]
    prog_id = created_program["id"]
    
    # Associate with batch if provided
    if batch_id:
        supabase.table("class_programs").insert({
            "class_id": batch_id,
            "program_id": prog_id
        }).execute()
    
    if course_ids:
        for i, c_id in enumerate(course_ids):
            supabase.table("program_courses").insert({
                "program_id": prog_id,
                "course_id": c_id,
                "sort_order": i
            }).execute()
            
    if mentor_ids:
        ment_res = supabase.table("mentors").select("id, parent_id").in_("parent_id", mentor_ids).execute()
        for m in (ment_res.data or []):
            supabase.table("course_mentors").insert({
                "program_id": prog_id,
                "mentor_id": m["id"]
            }).execute()
            
    return created_program

@router.put("/programs/{course_id}")
async def update_program(course_id: str, body: ProgramUpdate, current_user: dict = Depends(admin_required)):
    existing = supabase.table("programs").select("id").eq("id", course_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Program/course tidak ditemukan")
        
    data = body.model_dump(exclude_none=True)
    course_ids = data.pop("course_ids", None)
    batch_id = data.pop("batch_id", None)
    mentor_ids = data.pop("mentor_ids", None)
    
    res = supabase.table("programs").update(data).eq("id", course_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui program/course")
        
    updated_program = res.data[0]
    
    # Update batch association if provided
    if batch_id is not None:
        supabase.table("class_programs").delete().eq("program_id", course_id).execute()
        if batch_id:
            supabase.table("class_programs").insert({
                "class_id": batch_id,
                "program_id": course_id
            }).execute()

    if course_ids is not None:
        supabase.table("program_courses").delete().eq("program_id", course_id).execute()
        for i, c_id in enumerate(course_ids):
            supabase.table("program_courses").insert({
                "program_id": course_id,
                "course_id": c_id,
                "sort_order": i
            }).execute()

    if mentor_ids is not None:
        supabase.table("course_mentors").delete().eq("program_id", course_id).execute()
        ment_res = supabase.table("mentors").select("id, parent_id").in_("parent_id", mentor_ids).execute()
        for m in (ment_res.data or []):
            supabase.table("course_mentors").insert({
                "program_id": course_id,
                "mentor_id": m["id"]
            }).execute()
            
    return updated_program

@router.delete("/programs/{course_id}")
async def delete_program(course_id: str, current_user: dict = Depends(admin_required)):
    existing = supabase.table("programs").select("id").eq("id", course_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Program/course tidak ditemukan")
        
    res = supabase.table("programs").delete().eq("id", course_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menghapus program/course")
        
    return {"message": "Program/course berhasil dihapus"}

@router.get("/programs/{course_id}/students")
async def get_program_students(course_id: str, current_user: dict = Depends(admin_required)):
    """Get all enrolled students for a program (aggregated from all linked classes)"""
    # Verify program exists
    prog_res = supabase.table("programs").select("id, title").eq("id", course_id).execute()
    if not prog_res.data:
        raise HTTPException(status_code=404, detail="Program tidak ditemukan")
    
    # Get linked classes
    classes_res = supabase.table("classes").select("id, display_name").eq("course_id", course_id).execute()
    linked_classes = classes_res.data or []
    
    students = []
    for cls in linked_classes:
        enr_res = supabase.table("enrollments").select("student_id, enrolled_at, status").eq("class_id", cls["id"]).eq("status", "active").execute()
        for enr in (enr_res.data or []):
            # Get student details
            st_res = supabase.table("students").select("id, name, age, gender, parents(name, email, whatsapp_number)").eq("id", enr["student_id"]).execute()
            if st_res.data:
                st = st_res.data[0]
                parent = st.get("parents") or {}
                students.append({
                    "student_id": st["id"],
                    "student_name": st.get("name"),
                    "student_age": st.get("age"),
                    "student_gender": st.get("gender"),
                    "parent_name": parent.get("name"),
                    "parent_email": parent.get("email"),
                    "parent_whatsapp": parent.get("whatsapp_number"),
                    "class_name": cls["display_name"],
                    "class_id": cls["id"],
                    "enrolled_at": enr.get("enrolled_at"),
                })
    
    return {
        "program": prog_res.data[0],
        "total_enrolled": len(students),
        "students": students
    }


# ─── Program Student Management & Course Tools ───────────────

@router.get("/programs/{course_id}/all-students")
async def get_program_all_students(course_id: str, current_user: dict = Depends(admin_required)):
    """Get ALL students + their enrollment status in this program"""
    prog_res = supabase.table("programs").select("id, title").eq("id", course_id).execute()
    if not prog_res.data:
        raise HTTPException(status_code=404, detail="Program tidak ditemukan")
    
    # Get courses linked to this program
    pc_res = supabase.table("program_courses").select("course_id").eq("course_id", course_id).execute()
    course_ids = [row["course_id"] for row in pc_res.data] if pc_res.data else []
    
    # Get all enrollments (active OR waitlisted) for this program's courses
    enrolled_student_ids = set()
    waitlisted_student_ids = set()
    student_class_map = {}  # student_id -> class_id
    if course_ids:
        enr_res = supabase.table("enrollments").select("student_id, class_id, status").in_("course_id", course_ids).execute()
        for e in (enr_res.data or []):
            if e["status"] == "active":
                enrolled_student_ids.add(e["student_id"])
            elif e["status"] == "waitlisted":
                waitlisted_student_ids.add(e["student_id"])
            if e.get("class_id"):
                student_class_map[e["student_id"]] = e["class_id"]
    
    # Union: only students who belong to this batch can appear here
    batch_student_ids = enrolled_student_ids | waitlisted_student_ids
    # Get batch info from class_programs linkage for this program
    cp_res = supabase.table("class_programs").select("class_id").eq("course_id", course_id).execute()
    program_class_id = cp_res.data[0]["class_id"] if cp_res.data else None
    
    # Safety net: also include students with paid registrations for this program's class
    # (in case enrollment creation was missed during approval)
    if program_class_id:
        reg_res = supabase.table("registrations").select("student_id").eq("class_id", program_class_id).eq("status", "paid").execute()
        for r in (reg_res.data or []):
            batch_student_ids.add(r["student_id"])
            if r["student_id"] not in student_class_map:
                student_class_map[r["student_id"]] = program_class_id
    
    # Exclude students already active in a DIFFERENT program in same batch
    if program_class_id and batch_student_ids:
        active_res = supabase.table("enrollments").select("student_id, course_id") \
            .eq("class_id", program_class_id).eq("status", "active").execute()
        other_prog_sids = set()
        for ea in (active_res.data or []):
            if ea.get("course_id") and ea["course_id"] != course_id:
                other_prog_sids.add(ea["student_id"])
        batch_student_ids -= other_prog_sids
    
    # Fetch all classes for name resolution
    cls_res = supabase.table("classes").select("id, display_name").execute()
    class_map = {c["id"]: c["display_name"] for c in (cls_res.data or [])}
    program_batch_name = class_map.get(program_class_id) if program_class_id else None
    
    # Fetch only students who belong to this batch
    result = []
    if batch_student_ids:
        st_res = supabase.table("students").select("*").in_("id", list(batch_student_ids)).execute()
        for s in (st_res.data or []):
            p_res = supabase.table("parents").select("name, email").eq("id", s["parent_id"]).execute()
            parent = p_res.data[0] if p_res.data else {}
            
            sid = s["id"]
            is_enrolled = sid in enrolled_student_ids
            class_id = student_class_map.get(sid)
            batch_name = class_map.get(class_id) if class_id else program_batch_name
            
            result.append({
                "student_id": sid,
                "student_name": s.get("name"),
                "student_age": s.get("age"),
                "student_gender": s.get("gender"),
                "parent_name": parent.get("name"),
                "parent_email": parent.get("email"),
                "enrolled": is_enrolled,
                "batch_name": batch_name,
                "class_id": class_id,
            })
    
    result.sort(key=lambda x: (not x["enrolled"], x["student_name"] or ""))
    
    return {
        "program": prog_res.data[0],
        "total_students": len(result),
        "total_enrolled": len(enrolled_student_ids),
        "students": result
    }


@router.post("/programs/{course_id}/toggle-student")
async def toggle_program_student(course_id: str, body: StudentToggleEnrollment, current_user: dict = Depends(admin_required)):
    """Enroll or unenroll (waitlist) a student from this program's courses"""
    prog_res = supabase.table("programs").select("id").eq("id", course_id).execute()
    if not prog_res.data:
        raise HTTPException(status_code=404, detail="Program tidak ditemukan")
    
    pc_res = supabase.table("program_courses").select("course_id").eq("course_id", course_id).execute()
    course_ids = [row["course_id"] for row in pc_res.data] if pc_res.data else []
    
    cp_res = supabase.table("class_programs").select("class_id").eq("course_id", course_id).limit(1).execute()
    class_id = cp_res.data[0]["class_id"] if cp_res.data else None
    if not class_id:
        class_res = supabase.table("classes").select("id").eq("course_id", course_id).limit(1).execute()
        if class_res.data:
            class_id = class_res.data[0]["id"]
    
    student_id = body.student_id
    
    if not course_ids:
        raise HTTPException(status_code=400, detail="Program ini belum memiliki materi. Tambahkan materi terlebih dahulu.")
    
    if body.enrolled:
        # 1-student-1-course: waitlist any other active enrollment in same batch first
        if class_id:
            other_active = supabase.table("enrollments").select("id, course_id").eq("student_id", student_id).eq("class_id", class_id).eq("status", "active").execute()
            for oa in (other_active.data or []):
                # Don't waitlist if it's already one of target courses
                if oa["course_id"] not in course_ids:
                    supabase.table("enrollments").update({"status": "waitlisted", "course_id": None}).eq("id", oa["id"]).execute()
        
        for cid in course_ids:
            existing = supabase.table("enrollments").select("id, status").eq("student_id", student_id).eq("course_id", cid).execute()
            if existing.data:
                supabase.table("enrollments").update({"status": "active", "class_id": class_id, "course_id": course_id}).eq("id", existing.data[0]["id"]).execute()
            else:
                supabase.table("enrollments").insert({
                    "student_id": student_id,
                    "course_id": cid,
                    "class_id": class_id,
                    "course_id": course_id,
                    "status": "active"
                }).execute()
        return {"message": "Siswa berhasil ditambahkan ke program"}
    else:
        for cid in course_ids:
            existing = supabase.table("enrollments").select("id").eq("student_id", student_id).eq("course_id", cid).execute()
            if existing.data:
                supabase.table("enrollments").update({"status": "waitlisted", "course_id": None}).eq("id", existing.data[0]["id"]).execute()
        return {"message": "Siswa dipindahkan ke daftar tunggu (waitlist)"}


@router.post("/programs/{course_id}/reorder-courses")
async def reorder_program_courses(course_id: str, body: ProgramCourseReorder, current_user: dict = Depends(admin_required)):
    """Reorder bundled materials for a program"""
    supabase.table("program_courses").delete().eq("course_id", course_id).execute()
    for i, c_id in enumerate(body.course_ids):
        supabase.table("program_courses").insert({
            "course_id": course_id,
            "course_id": c_id,
            "sort_order": i
        }).execute()
    return {"message": "Urutan materi berhasil diperbarui"}


@router.get("/programs/{course_id}/mentors")
async def get_program_mentors(course_id: str, current_user: dict = Depends(admin_required)):
    """Get mentors assigned to a program"""
    cm_res = supabase.table("course_mentors").select("mentor_id").eq("course_id", course_id).execute()
    mentor_ids = [row["mentor_id"] for row in cm_res.data] if cm_res.data else []
    mentors = []
    if mentor_ids:
        m_res = supabase.table("mentors").select("id, parent_id, bio, expertise").in_("id", mentor_ids).execute()
        for m in (m_res.data or []):
            p_res = supabase.table("parents").select("name, email").eq("id", m["parent_id"]).execute()
            parent = p_res.data[0] if p_res.data else {}
            mentors.append({
                "mentor_id": m["id"],
                "mentor_name": parent.get("name"),
                "mentor_email": parent.get("email"),
                "bio": m.get("bio"),
                "expertise": m.get("expertise")
            })
    return {"mentors": mentors}


# ─── Batches CRUD ───────────────────────────────────

@router.get("/batches")
async def list_batches(current_user: dict = Depends(admin_required)):
    res = supabase.table("classes").select("*").execute()
    batches = res.data or []
    for b in batches:
        class_id = b["id"]
        b["status"] = b.get("status") or "open"

        # 1. Get linked course_ids and sum their quotas
        cp_res = supabase.table("class_programs").select("program_id").eq("class_id", class_id).execute()
        course_ids = [row["program_id"] for row in cp_res.data] if cp_res.data else []
        
        # Fallback to legacy single course_id
        if not course_ids and b.get("course_id"):
            course_ids = [b["course_id"]]
        
        b["course_ids"] = course_ids
        
        # 2. Populate program_titles and calculate total_max
        program_titles = []
        total_max = 0
        if course_ids:
            p_res = supabase.table("programs").select("title, max_quota, is_active").in_("id", course_ids).execute()
            if p_res.data:
                for p in p_res.data:
                    program_titles.append(p["title"])
                    if p.get("is_active", True):
                        total_max += p.get("max_quota", 0)
        
        b["program_titles"] = program_titles
        b["program_title"] = ", ".join(program_titles) if program_titles else None
        
        # 3. Get course_ids (bundled from programs + manual class_materi)
        all_course_ids = set()
        if course_ids:
            pc_res = supabase.table("program_courses").select("course_id").in_("course_id", course_ids).execute()
            if pc_res.data:
                for row in pc_res.data:
                    all_course_ids.add(row["course_id"])
                    
        cc_res = supabase.table("class_materi").select("course_id").eq("class_id", class_id).execute()
        b["course_ids"] = list(all_course_ids.union([row["course_id"] for row in cc_res.data])) if cc_res.data else list(all_course_ids)
        
        # Populate course_titles
        course_titles = []
        if b["course_ids"]:
            c_res = supabase.table("courses").select("title").in_("id", b["course_ids"]).execute()
            if c_res.data:
                course_titles = [r["title"] for r in c_res.data]
        b["course_titles"] = course_titles

        # Legacy fallback course_title
        course_title = None
        if b.get("course_id"):
            c_res = supabase.table("courses").select("title").eq("id", b["course_id"]).execute()
            if c_res.data:
                course_title = c_res.data[0]["title"]
        b["course_title"] = course_title
        
        # 4. Dynamic quota calculation
        if not b["course_ids"]:
            total_max = 0
        elif total_max == 0:
            total_max = b.get("max_quota") or 0
            
        enroll_res = supabase.table("enrollments").select("id").eq("class_id", class_id).eq("status", "active").execute()
        filled = len(enroll_res.data) if enroll_res.data else 0
        
        b["max_quota"] = total_max
        b["filled_quota"] = filled
            
    return {"data": batches}

@router.post("/batches", status_code=201)
async def create_batch(body: BatchCreate, current_user: dict = Depends(admin_required)):
    data = body.model_dump(exclude_none=True)
    course_ids = data.pop("course_ids", None)
    course_ids = data.pop("course_ids", None)
    
    # Auto-bundle courses from Programs if course_ids not provided
    if not course_ids:
        all_course_ids = course_ids or []
        if data.get("course_id") and data["course_id"] not in all_course_ids:
            all_course_ids.append(data["course_id"])
            
        if all_course_ids:
            pc_res = supabase.table("program_courses").select("course_id").in_("course_id", all_course_ids).execute()
            if pc_res.data:
                course_ids = list(set(row["course_id"] for row in pc_res.data))
    
    res = supabase.table("classes").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat batch")
        
    created_batch = res.data[0]
    batch_id = created_batch["id"]
    
    # Save program relationships
    if course_ids:
        for p_id in course_ids:
            supabase.table("class_programs").insert({
                "class_id": batch_id,
                "program_id": p_id
            }).execute()
    elif created_batch.get("course_id"):
        supabase.table("class_programs").insert({
            "class_id": batch_id,
            "program_id": created_batch["course_id"]
        }).execute()

    # Save course relationships
    if course_ids:
        for c_id in course_ids:
            supabase.table("class_materi").insert({
                "class_id": batch_id,
                "course_id": c_id
            }).execute()
    elif created_batch.get("course_id"):
        supabase.table("class_materi").insert({
            "class_id": batch_id,
            "course_id": created_batch["course_id"]
        }).execute()
        
    return created_batch

@router.put("/batches/{batch_id}")
async def update_batch(batch_id: str, body: BatchUpdate, current_user: dict = Depends(admin_required)):
    existing = supabase.table("classes").select("id, name, category, course_id").eq("id", batch_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")
    existing_batch = existing.data[0]
        
    data = body.model_dump(exclude_none=True)
    course_ids = data.pop("course_ids", None)
    course_ids = data.pop("course_ids", None)
    
    # Update program relationships if course_ids was passed
    if course_ids is not None:
        supabase.table("class_programs").delete().eq("class_id", batch_id).execute()
        for p_id in course_ids:
            supabase.table("class_programs").insert({
                "class_id": batch_id,
                "program_id": p_id
            }).execute()
        
        # Auto-bundle courses from Programs if course_ids not provided
        if course_ids is None:
            pc_res = supabase.table("program_courses").select("course_id").in_("course_id", course_ids).execute()
            if pc_res.data:
                course_ids = list(set(row["course_id"] for row in pc_res.data))
    
    res = supabase.table("classes").update(data).eq("id", batch_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui batch")
        
    updated_batch = res.data[0]
    
    # Update courses in junction table if course_ids was passed or auto-loaded
    if course_ids is not None:
        supabase.table("class_materi").delete().eq("class_id", batch_id).execute()
        for c_id in course_ids:
            supabase.table("class_materi").insert({
                "class_id": batch_id,
                "course_id": c_id
            }).execute()
    elif "course_id" in data:
        # If single course_id updated, sync class_materi too
        supabase.table("class_materi").delete().eq("class_id", batch_id).execute()
        if data["course_id"]:
            supabase.table("class_materi").insert({
                "class_id": batch_id,
                "course_id": data["course_id"]
            }).execute()
            
    return updated_batch

@router.delete("/batches/{batch_id}")
async def delete_batch(batch_id: str, current_user: dict = Depends(admin_required)):
    existing = supabase.table("classes").select("id").eq("id", batch_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")
    
    # 1. Cleanup junction tables
    supabase.table("class_materi").delete().eq("class_id", batch_id).execute()
    supabase.table("class_programs").delete().eq("class_id", batch_id).execute()
    
    # 2. Cleanup enrollments (optional: usually we want to keep them, but if user wants to DELETE batch, we must handle this)
    # For now, let's just delete them to allow batch deletion
    supabase.table("enrollments").delete().eq("class_id", batch_id).execute()
    
    # 3. Disconnect registrations (don't delete financial records)
    supabase.table("registrations").update({"class_id": None}).eq("class_id", batch_id).execute()

    res = supabase.table("classes").delete().eq("id", batch_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menghapus batch. Pastikan tidak ada data terkait yang sangat penting.")
    return {"message": "Batch berhasil dihapus"}

@router.get("/batches/{batch_id}/members")
async def get_batch_members(batch_id: str, current_user: dict = Depends(admin_required)):
    # 1. Get Batch Info (Mentor)
    batch_res = supabase.table("classes").select("id, name, display_name, mentor_id").eq("id", batch_id).execute()
    if not batch_res.data:
        raise HTTPException(status_code=404, detail="Batch tidak ditemukan")
    batch = batch_res.data[0]
    
    # 2. Get Enrolled Students
    enroll_res = supabase.table("enrollments").select("id, student_id, status").eq("class_id", batch_id).execute()
    enrollments = enroll_res.data or []
    
    student_ids = [e["student_id"] for e in enrollments]
    students = []
    if student_ids:
        st_res = supabase.table("students").select("*").in_("id", student_ids).execute()
        students = st_res.data or []
        
        # Add enrollment status to student objects
        status_map = {e["student_id"]: e["status"] for e in enrollments}
        enroll_id_map = {e["student_id"]: e["id"] for e in enrollments}
        for s in students:
            s["enrollment_status"] = status_map.get(s["id"], "active")
            s["enrollment_id"] = enroll_id_map.get(s["id"])
            
            # Get parent info
            p_res = supabase.table("parents").select("name, email").eq("id", s["parent_id"]).execute()
            if p_res.data:
                s["parent_name"] = p_res.data[0]["name"]
                s["parent_email"] = p_res.data[0]["email"]

    return {
        "batch": batch,
        "mentor_id": batch.get("mentor_id"),
        "students": students
    }

class BatchMembersUpdate(BaseModel):
    mentor_id: Optional[str] = None
    student_ids: List[str] = []

@router.post("/batches/{batch_id}/members")
async def update_batch_members(batch_id: str, body: BatchMembersUpdate, current_user: dict = Depends(admin_required)):
    # 1. Update Mentor
    supabase.table("classes").update({"mentor_id": body.mentor_id or None}).eq("id", batch_id).execute()
    
    # 2. Get existing enrollments for this batch
    existing_res = supabase.table("enrollments").select("student_id").eq("class_id", batch_id).execute()
    existing_student_ids = [e["student_id"] for e in existing_res.data] if existing_res.data else []
    
    # Perform removals (Update to waitlisted instead of delete)
    to_remove = [sid for sid in existing_student_ids if sid not in body.student_ids]
    if to_remove:
        supabase.table("enrollments").update({"status": "waitlisted"}).eq("class_id", batch_id).in_("student_id", to_remove).execute()
        print(f"[MEMBERS] Moved {len(to_remove)} students to waitlist for batch {batch_id}")
        
    # Perform additions or reactivations
    if body.student_ids:
        # We need to know which courses are linked to this batch
        cc_res = supabase.table("class_materi").select("course_id").eq("class_id", batch_id).execute()
        course_ids = [row["course_id"] for row in cc_res.data] if cc_res.data else []
        if not course_ids:
            b_res = supabase.table("classes").select("course_id").eq("id", batch_id).execute()
            if b_res.data and b_res.data[0].get("course_id"):
                course_ids = [b_res.data[0]["course_id"]]

        for sid in body.student_ids:
            for cid in course_ids:
                # Upsert to 'active'
                existing = supabase.table("enrollments").select("id").eq("student_id", sid).eq("course_id", cid).eq("class_id", batch_id).execute()
                if existing.data:
                    supabase.table("enrollments").update({"status": "active"}).eq("id", existing.data[0]["id"]).execute()
                else:
                    supabase.table("enrollments").insert({
                        "student_id": sid,
                        "course_id": cid,
                        "class_id": batch_id,
                        "status": "active"
                    }).execute()
        print(f"[MEMBERS] Reactivated/Enrolled {len(body.student_ids)} students as active for batch {batch_id}")

    # 3. Sync filled_quota & status
    try:
        count_res = supabase.table("enrollments").select("student_id", count="exact").eq("class_id", batch_id).eq("status", "active").execute()
        # Note: we want DISTINCT students, but exact count on student_id filtering is usually enough if schema is consistent.
        # To be safe, fetch all and count in python since it's admin portal.
        active_res = supabase.table("enrollments").select("student_id").eq("class_id", batch_id).eq("status", "active").execute()
        active_student_ids = list(set([e["student_id"] for e in active_res.data])) if active_res.data else []
        new_filled_q = len(active_student_ids)

        # Recalculate status
        cc_quota_res = supabase.table("class_materi").select("course_id").eq("class_id", batch_id).execute()
        linked_course_ids = [row["course_id"] for row in cc_quota_res.data] if cc_quota_res.data else []
        
        total_max = 0
        if linked_course_ids:
            p_res = supabase.table("programs").select("max_quota").in_("id", linked_course_ids).eq("is_active", True).execute()
            if p_res.data:
                total_max = sum(p.get("max_quota", 0) for p in p_res.data)
        
        class_info = supabase.table("classes").select("max_quota").eq("id", batch_id).execute()
        if class_info.data:
            c_data = class_info.data[0]
            if total_max == 0:
                total_max = c_data.get("max_quota") or 0
            
            update_payload = {"filled_quota": new_filled_q}
            if total_max > 0:
                if new_filled_q >= total_max:
                    update_payload["status"] = "full"
                elif new_filled_q >= int(total_max * 0.8):
                    update_payload["status"] = "almost_full"
                else:
                    update_payload["status"] = "open"
            
            supabase.table("classes").update(update_payload).eq("id", batch_id).execute()
            print(f"[MEMBERS] Synced filled_quota for batch {batch_id} to {new_filled_q} (Max: {total_max})")
    except Exception as e:
        print(f"[MEMBERS] Quota sync failed: {e}")

    return {"message": "Batch members updated successfully"}


# ─── Enrollments CRUD ────────────────────────────────

@router.get("/enrollments")
async def list_enrollments(current_user: dict = Depends(admin_required)):
    res = supabase.table("enrollments").select("*").execute()
    enrollments = res.data or []
    for e in enrollments:
        student_name = "Siswa"
        if e.get("student_id"):
            st_res = supabase.table("students").select("name").eq("id", e["student_id"]).execute()
            if st_res.data:
                student_name = st_res.data[0]["name"]
        course_title = "Course"
        if e.get("course_id"):
            if e.get("status") == "waitlisted":
                course_title = "—"
            else:
                c_res = supabase.table("courses").select("title").eq("id", e["course_id"]).execute()
                if c_res.data:
                    course_title = c_res.data[0]["title"]
        batch_name = "Belum Terhubung"
        if e.get("class_id"):
            cl_res = supabase.table("classes").select("display_name, name").eq("id", e["class_id"]).execute()
            if cl_res.data:
                batch_name = cl_res.data[0].get("display_name") or cl_res.data[0].get("name")
        e["student_name"] = student_name
        e["course_title"] = course_title
        e["batch_name"] = batch_name
    return {"data": enrollments}

@router.post("/enrollments", status_code=201)
async def create_enrollment(body: EnrollmentCreate, current_user: dict = Depends(admin_required)):
    st_res = supabase.table("students").select("id").eq("id", body.student_id).execute()
    if not st_res.data:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    c_res = supabase.table("courses").select("id").eq("id", body.course_id).execute()
    if not c_res.data:
        raise HTTPException(status_code=404, detail="Course tidak ditemukan")
    
    if body.class_id:
        cl_res = supabase.table("classes").select("id").eq("id", body.class_id).execute()
        if not cl_res.data:
            raise HTTPException(status_code=404, detail="Batch tidak ditemukan")

    # Check if student is already in another active course
    if body.status == "active":
        active_enroll = supabase.table("enrollments")\
            .select("id")\
            .eq("student_id", body.student_id)\
            .eq("status", "active")\
            .execute()
        if active_enroll.data:
            raise HTTPException(
                status_code=400,
                detail="Siswa sudah terdaftar dalam course aktif lain. Silakan selesaikan atau nonaktifkan course tersebut terlebih dahulu."
            )

    existing = supabase.table("enrollments").select("id").eq("student_id", body.student_id).eq("course_id", body.course_id).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Enrollment sudah ada")

    data = body.model_dump(exclude_none=True)
    res = supabase.table("enrollments").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat enrollment")
    return res.data[0]

@router.put("/enrollments/{enrollment_id}")
async def update_enrollment(enrollment_id: str, body: EnrollmentUpdate, current_user: dict = Depends(admin_required)):
    existing = supabase.table("enrollments").select("id, student_id").eq("id", enrollment_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Enrollment tidak ditemukan")
    
    student_id = existing.data[0]["student_id"]
    if body.status == "active":
        active_enroll = supabase.table("enrollments")\
            .select("id")\
            .eq("student_id", student_id)\
            .eq("status", "active")\
            .neq("id", enrollment_id)\
            .execute()
        if active_enroll.data:
            raise HTTPException(
                status_code=400,
                detail="Siswa sudah terdaftar dalam course aktif lain. Silakan selesaikan atau nonaktifkan course tersebut terlebih dahulu."
            )

    res = supabase.table("enrollments").update({"status": body.status}).eq("id", enrollment_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui enrollment")
    return res.data[0]

@router.delete("/enrollments/{enrollment_id}")
async def delete_enrollment(enrollment_id: str, current_user: dict = Depends(admin_required)):
    existing = supabase.table("enrollments").select("id, class_id, status").eq("id", enrollment_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Enrollment tidak ditemukan")
    
    enroll_data = existing.data[0]
    class_id = enroll_data.get("class_id")
    was_active = enroll_data.get("status") == "active"

    res = supabase.table("enrollments").delete().eq("id", enrollment_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menghapus enrollment")
    
    # If deleted enrollment was active, decrement filled_quota
    if was_active and class_id:
        try:
            class_res = supabase.table("classes").select("filled_quota").eq("id", class_id).execute()
            if class_res.data:
                current_q = class_res.data[0].get("filled_quota") or 0
                new_q = max(0, current_q - 1)
                supabase.table("classes").update({"filled_quota": new_q}).eq("id", class_id).execute()
                print(f"[DELETE_ENROLL] Decremented filled_quota for {class_id} to {new_q}")
        except Exception as ex:
            print(f"[DELETE_ENROLL] Failed to update class quota: {ex}")

    return {"message": "Enrollment berhasil dihapus"}


# ─── Certificates CRUD ───────────────────────────────

@router.get("/certificates")
async def list_certificates(current_user: dict = Depends(admin_required)):
    res = supabase.table("certificates").select("*").execute()
    certs = res.data or []
    for c in certs:
        student_name = "Siswa"
        if c.get("student_id"):
            st_res = supabase.table("students").select("name").eq("id", c["student_id"]).execute()
            if st_res.data:
                student_name = st_res.data[0]["name"]
        c["student_name"] = student_name
    return {"data": certs}

@router.post("/certificates", status_code=201)
async def create_certificate(body: CertificateCreate, current_user: dict = Depends(admin_required)):
    st_res = supabase.table("students").select("id").eq("id", body.student_id).execute()
    if not st_res.data:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")
    
    data = body.model_dump(exclude_none=True)
    data["approved_by"] = str(current_user["id"])
    data["approved_at"] = datetime.now().isoformat()
    if data.get("status") == "issued":
        data["issued_at"] = datetime.now().isoformat()
    if not data.get("file_url"):
        safe_number = data["certificate_number"].replace("/", "-")
        data["file_url"] = f"/uploads/certificates/issued/{safe_number}.pdf"
    
    res = supabase.table("certificates").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat sertifikat")
    return res.data[0]

@router.post("/certificates/{certificate_id}/issue")
async def issue_certificate(certificate_id: str, current_user: dict = Depends(admin_required)):
    existing = supabase.table("certificates").select("*").eq("id", certificate_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Sertifikat tidak ditemukan")

    cert = existing.data[0]
    file_url = cert.get("file_url")
    if not file_url:
        safe_number = cert["certificate_number"].replace("/", "-")
        file_url = f"/uploads/certificates/issued/{safe_number}.pdf"

    res = supabase.table("certificates").update({
        "status": "issued",
        "file_url": file_url,
        "approved_by": str(current_user["id"]),
        "approved_at": datetime.now().isoformat(),
        "issued_at": datetime.now().isoformat(),
    }).eq("id", certificate_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menerbitkan sertifikat")
    return res.data[0]

@router.put("/certificates/{certificate_id}")
async def update_certificate(certificate_id: str, body: CertificateUpdate, current_user: dict = Depends(admin_required)):
    existing = supabase.table("certificates").select("id").eq("id", certificate_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Sertifikat tidak ditemukan")
    data = body.model_dump(exclude_none=True)
    res = supabase.table("certificates").update(data).eq("id", certificate_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui sertifikat")
    return res.data[0]

@router.delete("/certificates/{certificate_id}")
async def delete_certificate(certificate_id: str, current_user: dict = Depends(admin_required)):
    existing = supabase.table("certificates").select("id").eq("id", certificate_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Sertifikat tidak ditemukan")
    res = supabase.table("certificates").delete().eq("id", certificate_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menghapus sertifikat")
    return {"message": "Sertifikat berhasil dihapus"}


# ─── Schedules CRUD ──────────────────────────────────

@router.get("/schedules")
async def list_schedules(current_user: dict = Depends(admin_required)):
    res = supabase.table("schedules").select("*").execute()
    scheds = res.data or []
    for s in scheds:
        course_title = "Course"
        if s.get("course_id"):
            c_res = supabase.table("courses").select("title").eq("id", s["course_id"]).execute()
            if c_res.data:
                course_title = c_res.data[0]["title"]
        mentor_name = "Mentor"
        if s.get("mentor_id"):
            m_res = supabase.table("mentors").select("*").eq("id", s["mentor_id"]).execute()
            if m_res.data and m_res.data[0].get("parent_id"):
                account_res = supabase.table("parents").select("name").eq("id", m_res.data[0]["parent_id"]).execute()
                if account_res.data:
                    mentor_name = account_res.data[0]["name"]
        s["course_title"] = course_title
        s["mentor_name"] = mentor_name
    return {"data": scheds}

@router.post("/schedules", status_code=201)
async def create_schedule(body: ScheduleCreate, current_user: dict = Depends(admin_required)):
    data = body.model_dump(exclude_none=True)
    generate_zoom = data.pop("generate_zoom", False)
    
    if generate_zoom:
        import random
        meeting_id = "".join([str(random.randint(0, 9)) for _ in range(10)])
        data["zoom_meeting_id"] = meeting_id
        data["zoom_join_url"] = f"https://zoom.us/j/{meeting_id}"
        data["zoom_start_url"] = f"https://zoom.us/s/{meeting_id}"
        
    res = supabase.table("schedules").insert(data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat jadwal")
    return res.data[0]

@router.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, body: ScheduleUpdate, current_user: dict = Depends(admin_required)):
    existing = supabase.table("schedules").select("id").eq("id", schedule_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
    data = body.model_dump(exclude_none=True)
    res = supabase.table("schedules").update(data).eq("id", schedule_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal memperbarui jadwal")
    return res.data[0]

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, current_user: dict = Depends(admin_required)):
    existing = supabase.table("schedules").select("id").eq("id", schedule_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
    res = supabase.table("schedules").delete().eq("id", schedule_id).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menghapus jadwal")
    return {"message": "Jadwal berhasil dihapus"}


# ─── Final Reports Review ─────────────────────────────

class FinalReportReviewRequest(BaseModel):
    revision_notes: Optional[str] = None

@router.get("/final-reports")
async def list_final_reports(current_user: dict = Depends(admin_required)):
    res = supabase.table("final_reports").select("*").execute()
    reports = res.data or []
    for r in reports:
        r["student_name"] = "Siswa"
        if r.get("student_id"):
            st_res = supabase.table("students").select("name").eq("id", r["student_id"]).execute()
            if st_res.data:
                r["student_name"] = st_res.data[0]["name"]
                
        r["mentor_name"] = "Mentor"
        if r.get("mentor_id"):
            mentor_res = supabase.table("mentors").select("parent_id").eq("id", r["mentor_id"]).execute()
            if mentor_res.data:
                parent_id = mentor_res.data[0]["parent_id"]
                p_res = supabase.table("parents").select("full_name").eq("id", parent_id).execute()
                if p_res.data:
                    r["mentor_name"] = p_res.data[0]["full_name"]
                    
        r["course_title"] = "Course"
        if r.get("enrollment_id"):
            enroll_res = supabase.table("enrollments").select("course_id").eq("id", r["enrollment_id"]).execute()
            if enroll_res.data:
                course_id = enroll_res.data[0]["course_id"]
                c_res = supabase.table("courses").select("title").eq("id", course_id).execute()
                if c_res.data:
                    r["course_title"] = c_res.data[0]["title"]
    return {"data": reports}

@router.post("/final-reports/{id}/approve")
async def approve_final_report(id: UUID, current_user: dict = Depends(admin_required)):
    from datetime import datetime
    existing = supabase.table("final_reports").select("*").eq("id", str(id)).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Laporan akhir tidak ditemukan")
        
    payload = {
        "status": "approved",
        "reviewed_at": datetime.now().isoformat(),
        "published_at": datetime.now().isoformat()
    }
    
    res = supabase.table("final_reports").update(payload).eq("id", str(id)).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menyetujui laporan akhir")
        
    return {"message": "Laporan akhir berhasil disetujui", "data": res.data[0]}

@router.post("/final-reports/{id}/reject")
async def reject_final_report(id: UUID, body: FinalReportReviewRequest, current_user: dict = Depends(admin_required)):
    existing = supabase.table("final_reports").select("*").eq("id", str(id)).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Laporan akhir tidak ditemukan")
        
    payload = {
        "status": "revision_requested",
        "revision_notes": body.revision_notes or "Revisi diminta oleh Admin."
    }
    
    res = supabase.table("final_reports").update(payload).eq("id", str(id)).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal menolak laporan akhir")
        
    return {"message": "Laporan akhir berhasil dikirim kembali untuk revisi", "data": res.data[0]}


# ─── File Upload Endpoint ─────────────────────────────

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(admin_required)
):
    import os
    import uuid
    from app.services.storage import storage_client
    
    # Read file content
    content = await file.read()
    
    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    
    # Define R2 path
    r2_path = f"branding/thumbnails/{filename}"
    
    # Upload to R2
    storage_client.upload_file(r2_path, content, file.content_type)
    
    # Save to database
    file_record = {
        "filename": filename,
        "original_filename": file.filename,
        "mime_type": file.content_type,
        "file_path": r2_path,  # Use r2_path which is defined
        "file_url": f"/uploads/branding/thumbnails/{filename}",
        "file_size": len(content),  # Use len of content, not os.path
        "owner_id": current_user["id"]
    }
    supabase.table("file_uploads").insert(file_record).execute()
    
    # Return the relative path that the frontend expects
    return {"url": f"/uploads/{r2_path}"}


@router.get("/files")
async def list_files(current_user: dict = Depends(admin_required)):
    """List all uploaded files, syncing with physical storage first"""
    import os
    import mimetypes
    from datetime import datetime, timezone
    from app.core.config import settings

    storage_path = settings.STORAGE_PATH
    if not storage_path or not os.path.exists(storage_path):
        res = supabase.table("file_uploads").select("*").order("created_at", desc=True).execute()
        return {"data": res.data or []}

    # 1. Fetch all existing database records
    db_res = supabase.table("file_uploads").select("*").execute()
    db_records = db_res.data or []
    db_by_path = {r["file_path"]: r for r in db_records}
    db_by_url = {r["file_url"]: r for r in db_records}

    new_records = []

    # 2. Recursively scan the physical storage
    for root, dirs, files in os.walk(storage_path):
        for file in files:
            full_path = os.path.join(root, file)
            if not os.path.isfile(full_path):
                continue

            # Check if this file path is already tracked
            if full_path in db_by_path:
                continue

            # Get relative path and URL format
            rel_path = os.path.relpath(full_path, storage_path)
            rel_path_url = rel_path.replace("\\", "/")
            file_url = f"/uploads/{rel_path_url}"

            # Skip if URL already tracked differently
            if file_url in db_by_url:
                continue

            # Guess mime type
            mime_type, _ = mimetypes.guess_type(full_path)
            if not mime_type:
                ext = os.path.splitext(file)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    mime_type = f"image/{ext[1:] if ext != '.jpg' else 'jpeg'}"
                elif ext == '.pdf':
                    mime_type = "application/pdf"
                else:
                    mime_type = "application/octet-stream"

            # Get file size
            try:
                file_size = os.path.getsize(full_path)
            except Exception:
                file_size = 0

            # Get creation time
            try:
                ctime = os.path.getctime(full_path)
                created_at = datetime.fromtimestamp(ctime, tz=timezone.utc).isoformat()
            except Exception:
                created_at = datetime.now(timezone.utc).isoformat()

            new_record = {
                "filename": file,
                "original_filename": file,
                "mime_type": mime_type,
                "file_path": full_path,
                "file_url": file_url,
                "file_size": file_size,
                "owner_id": current_user["id"],
                "created_at": created_at,
                "updated_at": created_at
            }
            new_records.append(new_record)

    # 3. Bulk insert new discovered files
    if new_records:
        for i in range(0, len(new_records), 100):
            batch = new_records[i:i+100]
            try:
                supabase.table("file_uploads").insert(batch).execute()
            except Exception as e:
                print(f"[FILE SYNC] Error inserting batch: {e}")

    # 4. Clean up records for physical files that no longer exist
    for path, record in db_by_path.items():
        if not os.path.exists(path):
            try:
                supabase.table("file_uploads").delete().eq("id", record["id"]).execute()
            except Exception as e:
                print(f"[FILE SYNC] Error cleaning up orphaned DB record for {path}: {e}")

    # 5. Fetch and return list
    res = supabase.table("file_uploads").select("*").order("created_at", desc=True).execute()
    return {"data": res.data or []}


@router.delete("/files/{file_id}")
async def delete_file(file_id: str, current_user: dict = Depends(admin_required)):
    """Delete an uploaded file physically and clear all references in the database"""
    import os
    # 1. Fetch file record
    file_res = supabase.table("file_uploads").select("*").eq("id", file_id).execute()
    if not file_res.data:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
    
    file_record = file_res.data[0]
    file_path = file_record.get("file_path")
    file_url = file_record.get("file_url")

    # 2. Delete physical file from disk if it exists
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"[FILE DELETE] Error removing physical file {file_path}: {e}")

    # 3. Clean up database references
    # - courses (thumbnail)
    try:
        supabase.table("courses").update({"thumbnail": None}).eq("thumbnail", file_url).execute()
    except Exception as e:
        print(f"[FILE DELETE] Error clearing courses reference: {e}")

    # - final_reports (file_url)
    try:
        supabase.table("final_reports").update({"file_url": None}).eq("file_url", file_url).execute()
    except Exception as e:
        print(f"[FILE DELETE] Error clearing final_reports reference: {e}")

    # - certificates (file_url)
    try:
        supabase.table("certificates").update({"file_url": None}).eq("file_url", file_url).execute()
    except Exception as e:
        print(f"[FILE DELETE] Error clearing certificates reference: {e}")

    # - assignments (attachment_url)
    try:
        supabase.table("assignments").update({"attachment_url": None}).eq("attachment_url", file_url).execute()
    except Exception as e:
        print(f"[FILE DELETE] Error clearing assignments reference: {e}")

    # - certificate_templates (background_url)
    try:
        supabase.table("certificate_templates").update({"background_url": ""}).eq("background_url", file_url).execute()
    except Exception as e:
        print(f"[FILE DELETE] Error clearing certificate_templates reference: {e}")

    # - mentor_materials (delete record since file_url is NOT NULL)
    try:
        supabase.table("mentor_materials").delete().eq("file_url", file_url).execute()
    except Exception as e:
        print(f"[FILE DELETE] Error deleting mentor_materials reference: {e}")

    # - assignment_submissions (delete record since submission_url is NOT NULL)
    try:
        supabase.table("assignment_submissions").delete().eq("submission_url", file_url).execute()
    except Exception as e:
        print(f"[FILE DELETE] Error deleting assignment_submissions reference: {e}")

    # 4. Delete file_uploads record
    supabase.table("file_uploads").delete().eq("id", file_id).execute()

    return {"message": "File berhasil dihapus dan semua referensi telah dibersihkan"}

    # Return the relative path that the frontend expects
    return {"url": f"/uploads/{r2_path}"}


# ─── Catalog Layout Endpoints ─────────────────────────

@router.get("/catalog-layout")
async def get_admin_catalog_layout(current_user: dict = Depends(admin_required)):
    res = supabase.table("catalog_layout").select("*, classes(*)").order("order_index").execute()
    return {"data": res.data or []}

@router.put("/catalog-layout")
async def update_catalog_layout(body: list[dict], current_user: dict = Depends(admin_required)):
    supabase.table("catalog_layout").delete().execute()
    
    inserted = []
    for i, item in enumerate(body):
        payload = {
            "type": item["type"],
            "batch_id": item.get("batch_id"),
            "h1": item.get("h1"),
            "h2": item.get("h2"),
            "paragraph": item.get("paragraph"),
            "align": item.get("align", "center"),
            "color": item.get("color", "#F86300"),
            "order_index": i
        }
        res = supabase.table("catalog_layout").insert(payload).execute()
        if res.data:
            inserted.append(res.data[0])
    return {"data": inserted}


# ─── Achievements CRUD ─────────────────────────────

class AchievementCreate(BaseModel):
    title: str
    description: Optional[str] = None
    icon: str = "solar:star-bold"
    color: str = "#FFD700"
    category: str = "lesson"
    condition_type: str
    condition_value: int = 1
    sort_order: int = 0
    is_active: bool = True

class AchievementUpdate(AchievementCreate):
    pass


@router.get("/achievements")
async def list_achievements(current_user: dict = Depends(admin_required)):
    res = supabase.table("achievements").select("*").order("sort_order").execute()
    return {"data": res.data or []}


@router.post("/achievements")
async def create_achievement(body: AchievementCreate, current_user: dict = Depends(admin_required)):
    res = supabase.table("achievements").insert(body.model_dump()).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Gagal membuat achievement")
    return res.data[0]


@router.put("/achievements/{achievement_id}")
async def update_achievement(achievement_id: str, body: AchievementUpdate, current_user: dict = Depends(admin_required)):
    res = supabase.table("achievements").update(body.model_dump()).eq("id", achievement_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Achievement tidak ditemukan")
    return res.data[0]


@router.delete("/achievements/{achievement_id}")
async def delete_achievement(achievement_id: str, current_user: dict = Depends(admin_required)):
    supabase.table("achievements").delete().eq("id", achievement_id).execute()
    return {"message": "Achievement berhasil dihapus"}



