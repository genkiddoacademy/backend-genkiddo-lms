from fastapi import APIRouter, HTTPException, status
from app.schemas.pendaftaran import PromoValidateRequest
from app.core.postgre import supabase
from datetime import datetime, timezone

router = APIRouter()

@router.post("/validate")
async def validate_promo(request: PromoValidateRequest):
    try:
        # 1. Ambil data promo berdasarkan kode
        response = supabase.table("promo_codes").select("*").eq("code", request.code).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Kode promo tidak ditemukan.")
            
        promo = response.data[0]
        
        # 2. Cek status aktif
        if not promo.get("is_active", True):
            raise HTTPException(status_code=400, detail="Kode promo sudah tidak aktif.")

        # 3. Cek masa berlaku (Expired)
        if promo.get("expires_at"):
            # Pastikan format waktu sinkron dengan timezone UTC
            expires_at = datetime.fromisoformat(promo["expires_at"].replace("Z", "+00:00"))
            if expires_at < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Kode promo sudah kadaluarsa.")

        # 4. Cek kesesuaian kelas (applicable_class_ids)
        applicable_ids = promo.get("applicable_class_ids")
        # Jika array tidak kosong, pastikan class_id pendaftar ada di dalamnya
        if applicable_ids and str(request.class_id) not in applicable_ids:
            raise HTTPException(status_code=400, detail="Kode promo tidak berlaku untuk kelas ini.")
            
        # 5. Cek batas penggunaan (Max Usage) jika ada
        if promo.get("max_usage") is not None:
            used_count = promo.get("used_count", 0)
            if used_count >= promo["max_usage"]:
                raise HTTPException(status_code=400, detail="Batas penggunaan kode promo telah habis.")

        # 6. Cek minimal jumlah anak terdaftar (min_children) jika ada
        min_children = promo.get("min_children") or 0
        if min_children > 0:
            if not request.parent_email:
                raise HTTPException(status_code=400, detail="Kode promo ini memerlukan informasi email orang tua.")
            
            parent_res = supabase.table("parents").select("id").eq("email", request.parent_email).execute()
            if parent_res.data:
                parent_id = parent_res.data[0]["id"]
                students_res = supabase.table("students").select("id").eq("parent_id", parent_id).execute()
                student_count = len(students_res.data) if students_res.data else 0
            else:
                student_count = 0
            
            total_children = student_count + request.batch_count
            if total_children < min_children:
                raise HTTPException(
                    status_code=400,
                    detail=f"Kode promo ini hanya berlaku untuk pendaftaran minimal {min_children} anak. Jumlah anak terdaftar saat ini: {total_children}."
                )

        # Mengembalikan data lengkap agar frontend bisa menghitung/menampilkan dengan benar
        return {
            "valid": True,
            "label": promo.get("label", "Promo Berhasil!"),
            "discount_type": promo.get("discount_type"), # 'percentage' atau 'fixed'
            "discount_value": float(promo.get("discount_value", 0)),
            "description": promo.get("description")
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))