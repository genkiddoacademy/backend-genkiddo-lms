from fastapi import APIRouter, HTTPException, Depends, status, Query
from app.api.v1.endpoints.auth import require_role
from app.core.postgre import supabase
from app.schemas.shortlinks import ShortlinkCreate, ShortlinkUpdate, ShortlinkResponse
from typing import List, Optional
from uuid import UUID
import string
import random
import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import settings
from pydantic import BaseModel

router = APIRouter(tags=["Shortlinks"])
admin_required = require_role("admin")

def generate_random_code(length: int = 6) -> str:
    # Huruf besar, huruf kecil, angka
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))

def get_unique_random_code() -> str:
    for _ in range(10):
        code = generate_random_code(6)
        res = supabase.table("shortlinks").select("id").eq("code", code).execute()
        if not res.data:
            return code
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Gagal menghasilkan kode unik untuk shortlink. Silakan coba lagi."
    )

# --- Admin Endpoints ---

@router.get("/admin/shortlinks", response_model=List[ShortlinkResponse])
async def list_shortlinks(
    search: Optional[str] = Query(None),
    current_user: dict = Depends(admin_required)
):
    query = supabase.table("shortlinks").select("*")
    res = query.execute()
    data = res.data or []
    
    if search:
        s = search.lower()
        data = [
            item for item in data 
            if s in item.get("code", "").lower() or s in item.get("original_url", "").lower()
        ]
        
    # Sort by created_at desc
    data = sorted(data, key=lambda x: x.get("created_at", ""), reverse=True)
    return data

@router.post("/admin/shortlinks", response_model=ShortlinkResponse)
async def create_shortlink(
    body: ShortlinkCreate,
    current_user: dict = Depends(admin_required)
):
    # 1. Tentukan/generate code
    code = body.code.strip() if body.code else ""
    if not code:
        code = get_unique_random_code()
    else:
        # Cek duplikasi jika kustom code diberikan
        res = supabase.table("shortlinks").select("id").eq("code", code).execute()
        if res.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Kode shortlink '{code}' sudah digunakan. Silakan gunakan kode lain."
            )
            
    # 2. Insert ke database
    payload = {
        "code": code,
        "original_url": body.original_url.strip(),
        "is_active": True,
        "clicks": 0,
        "expires_at": body.expires_at.isoformat() if body.expires_at else None
    }
    
    insert_res = supabase.table("shortlinks").insert(payload).execute()
    if not insert_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal menyimpan shortlink ke database."
        )
        
    return insert_res.data[0]

@router.put("/admin/shortlinks/{shortlink_id}", response_model=ShortlinkResponse)
async def update_shortlink(
    shortlink_id: UUID,
    body: ShortlinkUpdate,
    current_user: dict = Depends(admin_required)
):
    # Cek apakah data ada
    existing = supabase.table("shortlinks").select("id, code").eq("id", str(shortlink_id)).execute()
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shortlink tidak ditemukan."
        )
        
    code = body.code.strip()
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kode shortlink tidak boleh kosong."
        )
        
    # Cek konflik kode baru dengan data lain
    if code != existing.data[0]["code"]:
        conflict = supabase.table("shortlinks").select("id").eq("code", code).execute()
        if conflict.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Kode shortlink '{code}' sudah digunakan."
            )
            
    payload = {
        "code": code,
        "original_url": body.original_url.strip(),
        "is_active": body.is_active,
        "expires_at": body.expires_at.isoformat() if body.expires_at else None
    }
    
    # Set updated_at dynamically
    from datetime import datetime, timezone
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    update_res = supabase.table("shortlinks").update(payload).eq("id", str(shortlink_id)).execute()
    if not update_res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal memperbarui shortlink."
        )
        
    return update_res.data[0]

@router.delete("/admin/shortlinks/{shortlink_id}")
async def delete_shortlink(
    shortlink_id: UUID,
    current_user: dict = Depends(admin_required)
):
    res = supabase.table("shortlinks").delete().eq("id", str(shortlink_id)).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shortlink tidak ditemukan."
        )
    return {"message": "Shortlink berhasil dihapus"}

class BulkDeleteRequest(BaseModel):
    ids: List[UUID]

@router.post("/admin/shortlinks/bulk-delete")
async def bulk_delete_shortlinks(
    body: BulkDeleteRequest,
    current_user: dict = Depends(admin_required)
):
    if not body.ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Daftar ID shortlink yang akan dihapus kosong."
        )
    id_strings = [str(uid) for uid in body.ids]
    res = supabase.table("shortlinks").delete().in_("id", id_strings).execute()
    return {"message": f"Berhasil menghapus {len(body.ids)} shortlink."}

# --- Public Endpoints ---

@router.get("/shortlinks/resolve/{code}")
async def resolve_shortlink(code: str):
    try:
        res = supabase.table("shortlinks").select("is_active, original_url, expires_at").eq("code", code).execute()
        rows = res.data

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shortlink tidak ditemukan atau sudah dihapus."
            )

        row = rows[0]

        if not row["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shortlink ini sedang dinonaktifkan oleh administrator."
            )

        # Check expiration
        if row.get("expires_at"):
            from datetime import datetime, timezone
            expires_at_str = row["expires_at"]
            if isinstance(expires_at_str, str):
                from dateutil.parser import isoparse
                expires_at_utc = isoparse(expires_at_str).replace(tzinfo=timezone.utc)
            else:
                expires_at_utc = expires_at_str.astimezone(timezone.utc)
            if datetime.now(timezone.utc) > expires_at_utc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Shortlink ini sudah kedaluwarsa."
                )

        # Increment clicks
        click_res = supabase.table("shortlinks").select("clicks").eq("code", code).execute()
        current_clicks = click_res.data[0]["clicks"] if click_res.data else 0
        supabase.table("shortlinks").update({"clicks": (current_clicks or 0) + 1}).eq("code", code).execute()

        return {"original_url": row["original_url"]}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Resolve shortlink error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan pada server: {str(e)}"
        )
