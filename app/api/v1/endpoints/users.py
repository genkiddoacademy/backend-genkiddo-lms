from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.api.v1.endpoints.auth import get_current_user
from app.core.postgre import supabase

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    whatsapp_number: Optional[str] = None

@router.put("/profile")
async def update_profile(req: UpdateProfileRequest, current_user: dict = Depends(get_current_user)):
    if current_user.get("role") == "student":
        # Student profile update logic can be added later if needed
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Update profil langsung untuk siswa belum tersedia."
        )

    parent_id = current_user["id"]
    update_data = {}
    
    if req.name is not None:
        update_data["name"] = req.name
    if req.email is not None:
        # Check if email is already taken
        if req.email != current_user.get("email"):
            existing = supabase.table("parents").select("id").eq("email", str(req.email)).execute()
            if existing.data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email sudah digunakan oleh akun lain."
                )
        update_data["email"] = str(req.email)
    if req.whatsapp_number is not None:
        update_data["whatsapp_number"] = req.whatsapp_number

    if not update_data:
        return {"message": "Tidak ada data yang diperbarui.", "data": current_user}

    res = supabase.table("parents").update(update_data).eq("id", parent_id).execute()
    
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal memperbarui profil."
        )

    return {"message": "Profil berhasil diperbarui.", "data": res.data[0]}
