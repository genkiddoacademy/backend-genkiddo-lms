from fastapi import APIRouter, Request, HTTPException, Depends, Query
import httpx
from pydantic import BaseModel
from app.core.postgre import supabase
from app.core.config import settings
from app.api.deps import get_api_key

router = APIRouter(prefix="/api/payment", tags=["Payment"])

@router.post("/callback")
async def midtrans_callback(request: Request):
    data = await request.json()
    async with httpx.AsyncClient() as client:
        try:
            gateway_res = await client.post(
                f"{settings.GATEWAY_URL}/api/midtrans/callback",
                json=data
            )
            if gateway_res.status_code != 200:
                raise HTTPException(status_code=gateway_res.status_code, detail=gateway_res.text)
            return gateway_res.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Gateway connection error: {str(e)}")

@router.post("/charge")
async def charge_payment(
    registration_id: str, 
    payment_type: str, # "qris", "bank_transfer"
    bank: str = None, # "bca", "bni", etc
    _ = Depends(get_api_key)
):
    async with httpx.AsyncClient() as client:
        try:
            params = {
                "registration_id": registration_id,
                "payment_type": payment_type
            }
            if bank:
                params["bank"] = bank
                
            gateway_res = await client.post(
                f"{settings.GATEWAY_URL}/api/midtrans/charge",
                params=params,
                headers={"X-API-Key": settings.GATEWAY_API_KEY}
            )
            if gateway_res.status_code != 200:
                raise HTTPException(status_code=gateway_res.status_code, detail=gateway_res.text)
            return gateway_res.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Gateway connection error: {str(e)}")

@router.post("/check-status/{registration_id}")
async def check_payment_status(registration_id: str, _ = Depends(get_api_key)):
    async with httpx.AsyncClient() as client:
        try:
            gateway_res = await client.post(
                f"{settings.GATEWAY_URL}/api/midtrans/check-status/{registration_id}",
                headers={"X-API-Key": settings.GATEWAY_API_KEY}
            )
            if gateway_res.status_code != 200:
                raise HTTPException(status_code=gateway_res.status_code, detail=gateway_res.text)
            return gateway_res.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Gateway connection error: {str(e)}")

@router.get("/details/{registration_id}")
async def get_payment_details(registration_id: str, _ = Depends(get_api_key)):
    res = supabase.table("registrations").select("*, classes(display_name, subtitle, base_price), students(name)").eq("id", registration_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Registration not found")
    
    reg = res.data[0]
    
    qris_payload = None
    if reg.get("qris_payload"):
        try:
            import json
            qris_payload = json.loads(reg["qris_payload"])
        except Exception:
            qris_payload = reg["qris_payload"]
            
    return {
        "id": reg.get("id"),
        "status": reg.get("status"),
        "amount": reg.get("amount"),
        "final_amount": reg.get("final_amount"),
        "service_fee": reg.get("service_fee") or 0,
        "class_name": reg.get("classes", {}).get("display_name") if reg.get("classes") else "Kelas",
        "student_name": reg.get("students", {}).get("name") if reg.get("students") else "Siswa",
        "qris_payload": qris_payload
    }


@router.get("/group-details/{payment_group_id}")
async def get_group_payment_details(payment_group_id: str, _ = Depends(get_api_key)):
    """Fetch payment group details including all registrations."""
    pg_res = supabase.table("payment_groups").select("*").eq("id", payment_group_id).execute()
    if not pg_res.data:
        raise HTTPException(404, detail="Payment group not found")
    pg = pg_res.data[0]

    regs_res = supabase.table("registrations") \
        .select("*, classes(display_name, subtitle, base_price), students(name)") \
        .eq("payment_group_id", payment_group_id) \
        .execute()

    qris_payload = None
    if pg.get("midtrans_payload"):
        try:
            import json
            qris_payload = json.loads(pg["midtrans_payload"]) if isinstance(pg["midtrans_payload"], str) else pg["midtrans_payload"]
        except Exception:
            qris_payload = pg["midtrans_payload"]

    registrations = []
    for reg in regs_res.data or []:
        class_info = reg.get("classes") or {}
        student_info = reg.get("students") or {}
        registrations.append({
            "id": reg["id"],
            "class_name": class_info.get("display_name", "Kelas"),
            "student_name": student_info.get("name", "Siswa"),
            "amount": reg.get("amount"),
            "final_amount": reg.get("final_amount"),
        })

    # Check if a promo code is applied
    promo_code = None
    if regs_res.data:
        first_reg = regs_res.data[0]
        if first_reg.get("promo_code_id"):
            promo_res = supabase.table("promo_codes").select("code").eq("id", first_reg["promo_code_id"]).execute()
            if promo_res.data:
                promo_code = promo_res.data[0].get("code")

    return {
        "id": pg["id"],
        "status": pg["status"],
        "total_amount": pg.get("total_amount", 0),
        "service_fee": pg.get("service_fee", 0),
        "final_total": pg.get("final_total", 0),
        "midtrans_order_id": pg.get("midtrans_order_id"),
        "qris_payload": qris_payload,
        "registrations": registrations,
        "promo_code": promo_code,
    }


@router.delete("/group/{payment_group_id}")
async def cancel_payment_group(payment_group_id: str, _ = Depends(get_api_key)):
    """Cancel a pending payment group and delete its associated registrations."""
    pg_res = supabase.table("payment_groups").select("status").eq("id", payment_group_id).execute()
    if not pg_res.data:
        raise HTTPException(404, detail="Payment group not found")
        
    if pg_res.data[0]["status"] == "paid":
        raise HTTPException(400, detail="Cannot cancel a paid registration")
        
    # Delete registrations first (foreign key constraint)
    supabase.table("registrations").delete().eq("payment_group_id", payment_group_id).execute()
    
    # Delete payment group
    supabase.table("payment_groups").delete().eq("id", payment_group_id).execute()
    
    return {"message": "Pendaftaran berhasil dibatalkan"}


class ApplyPromoRequest(BaseModel):
    payment_group_id: str
    promo_code: str


@router.post("/apply-promo")
async def apply_promo(request: ApplyPromoRequest, _ = Depends(get_api_key)):
    """Apply a promo code to a pending payment group and recalculate registration amounts."""
    # 1. Fetch payment group
    pg_res = supabase.table("payment_groups").select("*").eq("id", request.payment_group_id).execute()
    if not pg_res.data:
        raise HTTPException(status_code=404, detail="Grup pembayaran tidak ditemukan.")
    pg = pg_res.data[0]
    
    if pg.get("status") == "paid":
        raise HTTPException(status_code=400, detail="Grup pembayaran sudah lunas, tidak bisa menggunakan promo.")
        
    # 2. Fetch parent email
    parent_res = supabase.table("parents").select("email").eq("id", pg["parent_id"]).execute()
    if not parent_res.data:
        raise HTTPException(status_code=404, detail="Data orang tua tidak ditemukan.")
    parent_email = parent_res.data[0]["email"]
    
    # 3. Fetch registrations in the group
    regs_res = supabase.table("registrations").select("id, class_id, amount").eq("payment_group_id", request.payment_group_id).execute()
    if not regs_res.data:
        raise HTTPException(status_code=404, detail="Tidak ada pendaftaran dalam grup pembayaran ini.")
    
    # We will validate and calculate the discount for each registration
    from app.api.v1.endpoints.register import calculate_discount
    
    total_final_amount = 0.0
    updates = []
    
    for reg in regs_res.data:
        final_price, promo_id = await calculate_discount(
            request.promo_code,
            str(reg["class_id"]),
            float(reg["amount"]),
            parent_email=parent_email,
            batch_count=len(regs_res.data)
        )
        total_final_amount += final_price
        updates.append({
            "id": reg["id"],
            "promo_code_id": promo_id,
            "final_amount": final_price
        })
        
    # 4. Perform database updates
    for update in updates:
        supabase.table("registrations").update({
            "promo_code_id": update["promo_code_id"],
            "final_amount": update["final_amount"]
        }).eq("id", update["id"]).execute()
        
    supabase.table("payment_groups").update({
        "total_amount": total_final_amount
    }).eq("id", request.payment_group_id).execute()
    
    return {"message": "Promo berhasil digunakan!", "total_amount": total_final_amount}



@router.post("/group-charge")
async def charge_group_payment(
    payment_group_id: str = Query(...),
    payment_type: str = Query(...),
    bank: str = Query(None),
    _ = Depends(get_api_key)
):
    """Proxy to gateway for group charge."""
    async with httpx.AsyncClient() as client:
        params = {"payment_group_id": payment_group_id, "payment_type": payment_type}
        if bank:
            params["bank"] = bank
        gateway_res = await client.post(
            f"{settings.GATEWAY_URL}/api/midtrans/group-charge",
            params=params,
            headers={"X-API-Key": settings.GATEWAY_API_KEY}
        )
        if gateway_res.status_code != 200:
            raise HTTPException(status_code=gateway_res.status_code, detail=gateway_res.text)
        return gateway_res.json()


@router.post("/group-check-status/{payment_group_id}")
async def check_group_payment_status(payment_group_id: str, _ = Depends(get_api_key)):
    """Proxy to gateway for group check status."""
    async with httpx.AsyncClient() as client:
        gateway_res = await client.post(
            f"{settings.GATEWAY_URL}/api/midtrans/group-check-status/{payment_group_id}",
            headers={"X-API-Key": settings.GATEWAY_API_KEY}
        )
        if gateway_res.status_code != 200:
            raise HTTPException(status_code=gateway_res.status_code, detail=gateway_res.text)
        return gateway_res.json()


from app.api.v1.endpoints.auth import get_current_user

@router.get("/history")
async def get_payment_history(current_user: dict = Depends(get_current_user)):
    parent_id = current_user["id"]
    
    # 1. Fetch children/students for this parent
    students_res = supabase.table("students").select("id, name").eq("parent_id", parent_id).execute()
    student_ids = [s["id"] for s in students_res.data] if students_res.data else []
    
    if not student_ids:
        return {"history": []}
        
    # 2. Fetch registrations/payments for these students
    regs_res = supabase.table("registrations")\
        .select("id, created_at, status, amount, final_amount, class_id, classes(name, display_name), students(name)")\
        .in_("student_id", student_ids)\
        .order("created_at", desc=True)\
        .execute()
        
    history = []
    for reg in (regs_res.data or []):
        class_info = reg.get("classes") or {}
        class_name = class_info.get("display_name") or class_info.get("name") or "Kelas"
        student_info = reg.get("students") or {}
        student_name = student_info.get("name") or "Anak"
        
        # Format date: "2026-06-07T03:52:33.107442+00:00" -> "07 Jun 2026"
        date_str = reg.get("created_at") or ""
        if date_str:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
                date_str = f"{dt.day:02d} {months[dt.month - 1]} {dt.year}"
            except Exception:
                pass
                
        # Format amount to IDR
        final_amt = reg.get("final_amount") or reg.get("amount") or 0.0
        amt_str = f"Rp {int(final_amt):,}".replace(",", ".")
        
        # Format status
        status_raw = reg.get("status")
        status_map = {
            "paid": "Lunas",
            "failed": "Gagal",
            "cancelled": "Dibatalkan",
            "expired": "Kedaluwarsa",
            "pending": "Pending",
            "bypassed": "Bypass Admin",
        }
        status_text = status_map.get(status_raw, status_raw.capitalize() if status_raw else "Pending")
        
        history.append({
            "id": reg.get("id"),
            "date": date_str,
            "plan": f"{class_name} ({student_name})",
            "amount": amt_str,
            "status": status_text,
            "class_id": str(reg.get("class_id")) if reg.get("class_id") else None
        })
        
    return {"history": history}

