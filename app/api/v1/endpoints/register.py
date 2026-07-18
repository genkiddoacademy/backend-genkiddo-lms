from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Depends
import httpx
from datetime import datetime, timezone
from typing import Optional
from app.schemas.pendaftaran import RegistrationRequest, BatchRegistrationRequest, RegistrationItem
from app.core.postgre import supabase
from app.core.config import settings
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()

async def calculate_discount(promo_code: str | None, class_id: str, base_price: float, parent_email: str | None = None, batch_count: int = 1) -> tuple[float, str | None]:
    if not promo_code:
        return base_price, None
        
    res = supabase.table("promo_codes").select("*").eq("code", promo_code).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Kode promo tidak valid.")
        
    promo = res.data[0]
    
    if not promo.get("is_active", True):
        raise HTTPException(status_code=400, detail="Kode promo sudah tidak aktif.")
        
    if promo.get("expires_at"):
        expires_at = datetime.fromisoformat(promo["expires_at"].replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Kode promo sudah kadaluarsa.")
            
    applicable_ids = promo.get("applicable_class_ids")
    if applicable_ids and class_id not in applicable_ids:
        raise HTTPException(status_code=400, detail="Kode promo tidak berlaku untuk kelas ini.")
        
    if promo.get("class_id") and promo["class_id"] != class_id:
        raise HTTPException(status_code=400, detail="Kode promo tidak berlaku untuk kelas ini.")
        
    # Check max usage if set
    if promo.get("max_usage") is not None:
        used_count = promo.get("used_count", 0)
        if used_count >= promo["max_usage"]:
            raise HTTPException(status_code=400, detail="Batas penggunaan kode promo telah habis.")

    # Check min_children requirement if set
    min_children = promo.get("min_children") or 0
    if min_children > 0:
        if not parent_email:
            raise HTTPException(status_code=400, detail="Kode promo ini memerlukan informasi email orang tua.")
        
        # Check if parent exists
        parent_res = supabase.table("parents").select("id").eq("email", parent_email).execute()
        if parent_res.data:
            parent_id = parent_res.data[0]["id"]
            students_res = supabase.table("students").select("id").eq("parent_id", parent_id).execute()
            student_count = len(students_res.data) if students_res.data else 0
        else:
            student_count = 0
            
        total_children = student_count + batch_count
        if total_children < min_children:
            raise HTTPException(
                status_code=400, 
                detail=f"Kode promo ini hanya berlaku untuk pendaftaran minimal {min_children} anak. Jumlah anak terdaftar saat ini: {total_children}."
            )
        
    discount_value = float(promo.get("discount_value", 0))
    discount_type = promo.get("discount_type", "fixed")
    
    if discount_type == "percentage":
        final_price = base_price * (1 - (discount_value / 100))
    else:
        final_price = base_price - discount_value
        
    return max(0.0, final_price), promo.get("id")

def format_whatsapp_number(phone: str) -> str:
    """
    Normalize any phone number format into WAHA chatId format (62xxx@c.us).
    Handles inputs like: 081234567890, 81234567890, 6281234567890, +6281234567890
    """
    # Remove all non-digit characters (spaces, dashes, plus signs, etc.)
    cleaned = "".join(char for char in phone if char.isdigit())
    
    # Handle various prefixes
    if cleaned.startswith("62"):
        pass  # Already correct international format
    elif cleaned.startswith("0"):
        cleaned = "62" + cleaned[1:]  # 0812... → 62812...
    else:
        # Raw number without any prefix (e.g., 812...) — add 62
        cleaned = "62" + cleaned
    
    return f"{cleaned}@c.us"

async def send_wa_notification(phone: str, parent_name: str, student_name: str):
    """Send 1 WA for single-child registration."""
    if not settings.WAHA_URL or not settings.WAHA_API_KEY:
        print(f"[WAHA] WAHA not configured. Skipped sending WA to {phone}")
        return
    
    chat_id = format_whatsapp_number(phone)
    message = f"Halo {parent_name}, terima kasih telah mendaftar di Genkiddo Academy untuk ananda {student_name}. Pendaftaran Anda sedang kami proses."
    payload = {
        "chatId": chat_id,
        "text": message,
        "session": "default"
    }
    headers = {
        "X-Api-Key": settings.WAHA_API_KEY,
        "Content-Type": "application/json"
    }
    url = f"{settings.WAHA_URL}/api/sendText"
    
    print(f"[WAHA] Sending WA to {chat_id} (original input: {phone})")
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                print(f"[WAHA] WA sent successfully to {chat_id}")
            else:
                print(f"[WAHA ERROR] Status {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[WAHA ERROR] Failed to send WA to {chat_id}: {e}")

async def send_wa_notification_batch(phone: str, parent_name: str, student_names: list[str]):
    """Send 1 consolidated WA for multiple children (batch registration)."""
    if not settings.WAHA_URL or not settings.WAHA_API_KEY:
        print(f"[WAHA] WAHA not configured. Skipped sending WA to {phone}")
        return
    
    if len(student_names) == 1:
        msg = f"Halo {parent_name}, terima kasih telah mendaftar di Genkiddo Academy untuk ananda {student_names[0]}. Pendaftaran Anda sedang kami proses."
    else:
        names_str = ", ".join(student_names[:-1]) + ", dan " + student_names[-1]
        msg = f"Halo {parent_name}, terima kasih telah mendaftar di Genkiddo Academy untuk ananda {names_str}. Pendaftaran Anda sedang kami proses."
    
    chat_id = format_whatsapp_number(phone)
    payload = {
        "chatId": chat_id,
        "text": msg,
        "session": "default"
    }
    headers = {
        "X-Api-Key": settings.WAHA_API_KEY,
        "Content-Type": "application/json"
    }
    url = f"{settings.WAHA_URL}/api/sendText"
    print(f"[WAHA] Batch WA to {chat_id} for {len(student_names)} children")
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                print(f"[WAHA] Batch WA sent successfully to {chat_id}")
            else:
                print(f"[WAHA ERROR] Status {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[WAHA ERROR] Failed to send WA to {chat_id}: {e}")

@router.get("/classes")
async def list_active_classes():
    res = supabase.table("classes").select("*").eq("is_active", True).execute()
    classes = res.data or []
    
    for cls in classes:
        class_id = cls["id"]
        
        # Get linked programs and sum their quotas
        cp_res = supabase.table("class_programs").select("program_id").eq("class_id", class_id).execute()
        program_ids = [row["program_id"] for row in cp_res.data] if cp_res.data else []
        
        # Fallback to legacy single program_id if no rows in class_programs
        if not program_ids and cls.get("program_id"):
            program_ids = [cls["program_id"]]
            
        total_max = 0
        if program_ids:
            p_res = supabase.table("programs").select("max_quota").in_("id", program_ids).eq("is_active", True).execute()
            if p_res.data:
                total_max = sum(p.get("max_quota", 0) for p in p_res.data)
        
        # If still 0, fallback to classes.max_quota (manual control)
        if total_max == 0:
            total_max = cls.get("max_quota") or 0
        
        # Count active enrollments for this class
        enroll_res = supabase.table("enrollments").select("id").eq("class_id", class_id).eq("status", "active").execute()
        filled = len(enroll_res.data) if enroll_res.data else 0
        
        cls["max_quota"] = total_max
        cls["filled_quota"] = filled
        
        # Recalculate status
        if total_max > 0:
            if filled >= total_max:
                cls["status"] = "full"
            elif filled >= int(total_max * 0.8):
                cls["status"] = "almost_full"
            elif cls.get("status") in ("full", "almost_full"):
                cls["status"] = "open"
        else:
            if not cls.get("status") in ("closed", "completed"):
                cls["status"] = "open"
    
    return {"data": classes}

@router.post("/daftar")
async def register_student(request: RegistrationRequest, background_tasks: BackgroundTasks):
    try:
        # Cek class harga dan kuota
        class_id_str = str(request.course.class_id)
        class_res = supabase.table("classes").select("base_price, status").eq("id", class_id_str).execute()
        if not class_res.data:
            raise HTTPException(status_code=404, detail="Kelas tidak ditemukan.")
        cls_data = class_res.data[0]
        base_price = float(cls_data.get("base_price", 0))

        # Check quota (aggregate from linked programs)
        cp_res = supabase.table("class_programs").select("program_id").eq("class_id", class_id_str).execute()
        program_ids = [row["program_id"] for row in cp_res.data] if cp_res.data else []
        
        if not program_ids and cls_data.get("program_id"):
            program_ids = [cls_data["program_id"]]
            
        total_max = 0
        if program_ids:
            p_res = supabase.table("programs").select("max_quota").in_("id", program_ids).eq("is_active", True).execute()
            if p_res.data:
                total_max = sum(p.get("max_quota", 0) for p in p_res.data)
        
        if total_max == 0:
            total_max = cls_data.get("max_quota") or 0
        
        enroll_res = supabase.table("enrollments").select("id").eq("class_id", class_id_str).eq("status", "active").execute()
        filled_quota = len(enroll_res.data) if enroll_res.data else 0
        
        cls_status = cls_data.get("status") or "open"
        if cls_status in ("closed", "completed") or (total_max > 0 and filled_quota >= total_max):
            raise HTTPException(status_code=400, detail="Kelas yang dipilih sudah penuh atau tidak menerima pendaftaran baru.")

        # Kalkulasi diskon
        final_price, promo_id = await calculate_discount(
            request.course.promo_code, 
            str(request.course.class_id), 
            base_price,
            parent_email=request.parent.parent_email
        )

        # 1. Simpan atau Update Parent
        parent_email = request.parent.parent_email
        existing_parent = supabase.table("parents").select("id").eq("email", parent_email).execute()
        
        if existing_parent.data:
            parent_id = existing_parent.data[0]["id"]
            parent_data = {
                "name": request.parent.parent_name,
                "whatsapp_number": request.parent.whatsapp_number,
                "city": request.parent.city,
                "source": request.parent.source
            }
            # Update dengan data terbaru
            supabase.table("parents").update(parent_data).eq("id", parent_id).execute()
        else:
            parent_data = {
                "email": parent_email,
                "name": request.parent.parent_name,
                "whatsapp_number": request.parent.whatsapp_number,
                "city": request.parent.city,
                "source": request.parent.source
            }
            parent_res = supabase.table("parents").insert(parent_data).execute()
            if not parent_res.data:
                raise HTTPException(status_code=500, detail="Gagal menyimpan data orang tua.")
            parent_id = parent_res.data[0]["id"]

        # 2. Simpan atau Update Student
        student_id = request.student.student_id
        student_data = {
            "parent_id": parent_id,
            "name": request.student.student_name,
            "age": request.student.student_age,
            "gender": request.student.student_gender,
            "coding_experience": request.student.coding_experience,
            "interests": request.student.interests,
            "school_origin": request.student.school_origin
        }
        
        target_sid = None
        if student_id:
            # Check if student exists and belongs to the parent
            existing_student = supabase.table("students").select("id").eq("id", str(student_id)).eq("parent_id", parent_id).execute()
            if existing_student.data:
                target_sid = existing_student.data[0]["id"]
            else:
                # Safety search by name
                existing_by_name = supabase.table("students").select("id").eq("parent_id", parent_id).eq("name", request.student.student_name).execute()
                if existing_by_name.data:
                    target_sid = existing_by_name.data[0]["id"]
                else:
                    raise HTTPException(status_code=404, detail="Data anak tidak ditemukan atau bukan milik Anda.")
        else:
            # SEARCH BY NAME (Prevention for Renewal duplicates)
            existing_by_name = supabase.table("students").select("id").eq("parent_id", parent_id).eq("name", request.student.student_name).execute()
            if existing_by_name.data:
                target_sid = existing_by_name.data[0]["id"]

        if target_sid:
            # Update student details
            supabase.table("students").update(student_data).eq("id", target_sid).execute()
            student_id = target_sid
        else:
            student_res = supabase.table("students").insert(student_data).execute()
            if not student_res.data:
                raise HTTPException(status_code=500, detail="Gagal menyimpan data siswa.")
            student_id = student_res.data[0]["id"]

        # 3. Simpan Registration
        reg_data = {
            "student_id": student_id,
            "class_id": str(request.course.class_id),
            "expectation": request.course.expectation,
            "promo_code_id": promo_id,
            "status": "pending",
            "amount": base_price,
            "final_amount": final_price
        }
        reg_res = supabase.table("registrations").insert(reg_data).execute()
        if not reg_res.data:
            raise HTTPException(status_code=500, detail="Gagal menyimpan pendaftaran.")

        # Kirim WA Notifikasi di background
        background_tasks.add_task(
            send_wa_notification, 
            request.parent.whatsapp_number, 
            request.parent.parent_name, 
            request.student.student_name
        )

        return {"message": "Pendaftaran berhasil", "status": "pending", "registration_id": reg_res.data[0]["id"]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/registrations/cancel")
async def cancel_pending_registrations(current_user: dict = Depends(get_current_user)):
    try:
        parent_id = current_user["id"]
        res = supabase.table("students").select("id").eq("parent_id", parent_id).execute()
        student_ids = [s["id"] for s in res.data] if res.data else []
        if not student_ids:
            return {"message": "No pending registrations"}
        
        for s_id in student_ids:
            supabase.table("registrations").update({"status": "cancelled"}).eq("student_id", s_id).eq("status", "pending").execute()
            
        return {"message": "Cancelled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/classes/catalog-layout")
async def get_public_catalog_layout():
    res = supabase.table("catalog_layout").select("*, classes(*)").order("order_index").execute()
    return {"data": res.data or []}


# ── Batch Registration (Multi-child, 1x payment) ──

@router.post("/daftar-batch")
async def register_students_batch(request: BatchRegistrationRequest, background_tasks: BackgroundTasks):
    """
    Register multiple children in 1 payment group.
    - All children must register for same class (enforced for simplicity)
    - Pricing calculated per-item with individual promo handling
    - Creates payment_groups record + individual registrations
    """
    try:
        if not request.items or len(request.items) == 0:
            raise HTTPException(400, detail="Minimal 1 anak harus didaftarkan.")

        # Validate all items use same class
        first_class_id = str(request.items[0].course.class_id)
        for item in request.items[1:]:
            if str(item.course.class_id) != first_class_id:
                raise HTTPException(400, detail="Semua anak harus mendaftar di kelas yang sama.")

        # Check class availability
        class_res = supabase.table("classes").select("base_price, status").eq("id", first_class_id).execute()
        if not class_res.data:
            raise HTTPException(404, detail="Kelas tidak ditemukan.")
        cls_data = class_res.data[0]
        base_price = float(cls_data.get("base_price", 0))

        if cls_data.get("status") in ("closed", "completed"):
            raise HTTPException(400, detail="Kelas sudah tutup.")

        # Quota check
        avail = _calculate_available_quota(first_class_id)
        if len(request.items) > avail:
            raise HTTPException(400, detail=f"Kuota tersisa {avail}, dibutuhkan {len(request.items)}.")

        # 1. Upsert parent
        parent_id = _upsert_parent(request.parent)

        # 2. Calculate pricing per item
        items_data = []
        total_final_amount = 0.0

        for item in request.items:
            final_price, promo_id = await calculate_discount(
                item.course.promo_code,
                first_class_id,
                base_price,
                parent_email=request.parent.parent_email,
                batch_count=len(request.items)
            )
            total_final_amount += final_price
            items_data.append({"item": item, "final_price": final_price, "promo_id": promo_id})

        # 3. Create payment group
        pg_res = supabase.table("payment_groups").insert({
            "parent_id": parent_id,
            "total_amount": total_final_amount,
            "status": "pending"
        }).execute()
        if not pg_res.data:
            raise HTTPException(500, detail="Gagal membuat grup pembayaran.")
        payment_group_id = pg_res.data[0]["id"]

        # 4. Insert each registration
        registration_ids = []
        student_names = []
        for data in items_data:
            item = data["item"]
            student_id = _upsert_student(parent_id, item.student)

            reg_data = {
                "student_id": student_id,
                "class_id": first_class_id,
                "expectation": item.course.expectation,
                "promo_code_id": data["promo_id"],
                "status": "pending",
                "amount": base_price,
                "final_amount": data["final_price"],
                "payment_group_id": payment_group_id,
            }
            reg_res = supabase.table("registrations").insert(reg_data).execute()
            if not reg_res.data:
                raise HTTPException(500, detail="Gagal menyimpan pendaftaran.")
            reg_id = reg_res.data[0]["id"]
            registration_ids.append(reg_id)
            student_names.append(item.student.student_name)

        # Send 1 consolidated WA for all children
        background_tasks.add_task(
            send_wa_notification_batch,
            request.parent.whatsapp_number,
            request.parent.parent_name,
            student_names,
        )

        return {
            "message": "Pendaftaran batch berhasil",
            "payment_group_id": payment_group_id,
            "registration_ids": registration_ids,
            "total_amount": total_final_amount,
            "student_count": len(request.items)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=str(e))


def _upsert_parent(parent_info) -> str:
    """Insert or update parent, return parent_id."""
    email = parent_info.parent_email
    existing = supabase.table("parents").select("id").eq("email", email).execute()
    if existing.data:
        pid = existing.data[0]["id"]
        supabase.table("parents").update({
            "name": parent_info.parent_name,
            "whatsapp_number": parent_info.whatsapp_number,
            "city": parent_info.city,
            "source": parent_info.source
        }).eq("id", pid).execute()
        return pid
    else:
        res = supabase.table("parents").insert({
            "email": email,
            "name": parent_info.parent_name,
            "whatsapp_number": parent_info.whatsapp_number,
            "city": parent_info.city,
            "source": parent_info.source
        }).execute()
        if not res.data:
            raise HTTPException(500, detail="Gagal menyimpan data orang tua.")
        return res.data[0]["id"]


def _upsert_student(parent_id: str, student_info) -> str:
    """Insert or update student, return student_id."""
    student_data = {
        "parent_id": parent_id,
        "name": student_info.student_name,
        "age": student_info.student_age,
        "gender": student_info.student_gender,
        "coding_experience": student_info.coding_experience,
        "interests": student_info.interests,
        "school_origin": student_info.school_origin
    }
    
    sid = None
    if student_info.student_id:
        sid = str(student_info.student_id)
        existing = supabase.table("students").select("id").eq("id", sid).eq("parent_id", parent_id).execute()
        if not existing.data:
            # If provided ID not found, try searching by name for safety
            existing_by_name = supabase.table("students").select("id").eq("parent_id", parent_id).eq("name", student_info.student_name).execute()
            if existing_by_name.data:
                sid = existing_by_name.data[0]["id"]
            else:
                raise HTTPException(404, detail="Data anak tidak ditemukan atau bukan milik Anda.")
    else:
        # SEARCH BY NAME if student_id is empty (Prevention for Renewal duplicates)
        existing_by_name = supabase.table("students").select("id").eq("parent_id", parent_id).eq("name", student_info.student_name).execute()
        if existing_by_name.data:
            sid = existing_by_name.data[0]["id"]

    if sid:
        supabase.table("students").update(student_data).eq("id", sid).execute()
        return sid
    else:
        res = supabase.table("students").insert(student_data).execute()
        if not res.data:
            raise HTTPException(500, detail="Gagal menyimpan data siswa.")
        return res.data[0]["id"]


def _calculate_available_quota(class_id: str) -> int:
    """Calculate remaining quota for a class."""
    cp_res = supabase.table("class_programs").select("program_id").eq("class_id", class_id).execute()
    program_ids = [r["program_id"] for r in cp_res.data] if cp_res.data else []
    if not program_ids:
        cls_res = supabase.table("classes").select("program_id, max_quota").eq("id", class_id).execute()
        if cls_res.data and cls_res.data[0].get("program_id"):
            program_ids = [cls_res.data[0]["program_id"]]

    total_max = 0
    if program_ids:
        p_res = supabase.table("programs").select("max_quota").in_("id", program_ids).eq("is_active", True).execute()
        if p_res.data:
            total_max = sum(p.get("max_quota", 0) for p in p_res.data)
    if total_max == 0:
        cls_res = supabase.table("classes").select("max_quota").eq("id", class_id).execute()
        if cls_res.data:
            total_max = cls_res.data[0].get("max_quota") or 0

    enroll_res = supabase.table("enrollments").select("id").eq("class_id", class_id).eq("status", "active").execute()
    filled = len(enroll_res.data) if enroll_res.data else 0
    return max(0, total_max - filled)