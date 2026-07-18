from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class ShortlinkCreate(BaseModel):
    code: Optional[str] = Field(default=None, description="Kode shortlink kustom (opsional)")
    original_url: str = Field(..., description="URL tujuan redirect")
    expires_at: Optional[datetime] = Field(default=None, description="Waktu kedaluwarsa shortlink")

class ShortlinkUpdate(BaseModel):
    code: str = Field(..., description="Kode/slug shortlink")
    original_url: str = Field(..., description="URL tujuan redirect")
    is_active: bool = Field(..., description="Status keaktifan shortlink")
    expires_at: Optional[datetime] = Field(default=None, description="Waktu kedaluwarsa shortlink")

class ShortlinkResponse(BaseModel):
    id: UUID
    code: str
    original_url: str
    is_active: bool
    clicks: int
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
