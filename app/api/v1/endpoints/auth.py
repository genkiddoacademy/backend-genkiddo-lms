from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from app.core.email import send_html_email
from app.core.email_templates import VERIFICATION_EMAIL_TEMPLATE, RESET_PASSWORD_EMAIL_TEMPLATE
from datetime import datetime, timedelta, timezone
from app.schemas.auth import (
    RegisterRequest, LoginRequest, LoginResponse,
    UserResponse, UserBase
)
from app.core.postgre import supabase
from app.core.auth import get_password_hash, verify_password, create_access_token
from app.core.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
security = HTTPBearer()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 3000


def _normalize_email(value: str) -> str:
    return str(value).strip().lower()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Tidak dapat memverifikasi kredensial",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[ALGORITHM]
        )
        sub: str = payload.get("sub")
        role: str = payload.get("role")
        if sub is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    if role == "student":
        import re
        uuid_pat = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
        res = None
        if uuid_pat.match(sub):
            res = supabase.table("students").select("*").eq("id", sub).execute()
        if not res or not res.data:
            res = supabase.table("students").select("*").eq("username", sub).execute()
        if not res.data:
            raise credentials_exception
        user = res.data[0]
        if user.get("status") in ("suspended", "archived"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun Anda dinonaktifkan."
            )
        user["role"] = "student"
        return user
    else:
        lookup_email = _normalize_email(sub)
        res = supabase.table("parents").select("*").eq("email", lookup_email).execute()
        if not res.data:
            res = supabase.table("parents").select("*").eq("id", sub).execute()
        if not res.data:
            raise credentials_exception
        user = res.data[0]
        if user.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun Anda telah dinonaktifkan oleh Admin."
            )
        if user.get("role") == "mentor":
            mentor_res = supabase.table("mentors").select("is_active").eq("parent_id", user["id"]).execute()
            mentor_profile = mentor_res.data[0] if mentor_res.data else None
            if mentor_profile and mentor_profile.get("is_active") is False:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Akun Anda telah dinonaktifkan oleh Admin."
                )
        return user


def require_role(role: str):
    def checker(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akses ditolak"
            )
        return current_user
    return checker


import secrets
from pydantic import BaseModel, EmailStr

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    password: str

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, background_tasks: BackgroundTasks):
    email = _normalize_email(req.email)
    existing = supabase.table("parents").select("id, password_hash, is_verified").eq("email", email).execute()
    
    verification_token = secrets.token_hex(20)
    password_hash = get_password_hash(req.password)
    
    if existing.data:
        parent = existing.data[0]
        
        # If parent already has a password, they already have a full account → reject
        if parent.get("password_hash"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email sudah terdaftar"
            )
        
        # Parent exists but without password (created from /daftar registration flow).
        # Upgrade this record with login credentials to preserve the parent_id link to students.
        update_data = {
            "name": req.name,
            "whatsapp_number": req.whatsapp_number,
            "password_hash": password_hash,
            "role": "parent",
            "is_verified": False,
            "verification_token": verification_token
        }
        res = supabase.table("parents").update(update_data).eq("id", parent["id"]).execute()
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gagal memperbarui data akun"
            )
    else:
        # Brand new parent — insert fresh record
        parent_data = {
            "email": email,
            "name": req.name,
            "whatsapp_number": req.whatsapp_number,
            "city": "",
            "source": "web",
            "password_hash": password_hash,
            "role": "parent",
            "is_verified": False,
            "verification_token": verification_token
        }
        res = supabase.table("parents").insert(parent_data).execute()
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gagal menyimpan data"
            )

    # Print verification link for debugging/development
    verification_url = f"{settings.BACKEND_URL}/api/v1/auth/verify-email?token={verification_token}"
    
    # Send HTML verification email via SMTP in background
    html_content = VERIFICATION_EMAIL_TEMPLATE.replace("{verification_url}", verification_url)
    background_tasks.add_task(
        send_html_email,
        to_email=email,
        subject="Verifikasi Akun GenKiddo Anda",
        html_content=html_content
    )
    
    print(f"\n[EMAIL SIMULATION] Verification email sent to {req.email}:\nLink: {verification_url}\n")

    return {"message": "Akun berhasil dibuat. Silakan cek email Anda untuk verifikasi.", "status": "ok"}


@router.get("/verify-email")
async def verify_email(token: str):
    res = supabase.table("parents").select("*").eq("verification_token", token).execute()
    if not res.data:
        from fastapi.responses import HTMLResponse
        error_html = f"""
        <!DOCTYPE html>
        <html lang="id">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verifikasi Gagal - GenKiddo Academy</title>
            <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800;900&display=swap" rel="stylesheet">
            <style>
                body {{
                    font-family: 'Poppins', sans-serif;
                    background-color: #FFFAF5;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    overflow: hidden;
                    position: relative;
                }}
                .orb-1 {{
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 400px;
                    height: 400px;
                    background: #EF7F1F;
                    opacity: 0.04;
                    border-radius: 50%;
                    transform: translate(-30%, -30%);
                    filter: blur(80px);
                    z-index: 1;
                }}
                .orb-2 {{
                    position: absolute;
                    bottom: 0;
                    right: 0;
                    width: 500px;
                    height: 500px;
                    background: #4EA8DE;
                    opacity: 0.04;
                    border-radius: 50%;
                    transform: translate(30%, 30%);
                    filter: blur(90px);
                    z-index: 1;
                }}
                .pattern {{
                    position: absolute;
                    inset: 0;
                    opacity: 0.2;
                    background-image: radial-gradient(#EF7F1F 0.5px, transparent 0.5px);
                    background-size: 24px 24px;
                    z-index: 1;
                }}
                .container {{
                    position: relative;
                    z-index: 10;
                    width: 90%;
                    max-width: 500px;
                    text-align: center;
                    padding: 20px 0;
                }}
                .logo-wrapper {{
                    background: white;
                    padding: 18px;
                    border-radius: 28px;
                    box-shadow: 0 15px 35px rgba(239, 127, 31, 0.1);
                    display: inline-block;
                    margin-bottom: 30px;
                }}
                .logo-img {{
                    height: 55px;
                    display: block;
                }}
                .card {{
                    background: white;
                    border-radius: 36px;
                    padding: 45px 35px;
                    box-shadow: 0 25px 60px -15px rgba(239, 127, 31, 0.12);
                    border: 1px solid rgba(239, 127, 31, 0.05);
                }}
                .error-icon-wrapper {{
                    width: 80px;
                    height: 80px;
                    border-radius: 50%;
                    background: #FEF2F2;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 25px auto;
                    color: #EF4444;
                    box-shadow: 0 10px 20px rgba(239, 68, 68, 0.1);
                }}
                h1 {{
                    color: #1F1F1F;
                    font-size: 26px;
                    font-weight: 900;
                    margin: 0 0 15px 0;
                    letter-spacing: -0.5px;
                }}
                p {{
                    color: #666;
                    font-size: 14px;
                    line-height: 1.7;
                    margin: 0 0 35px 0;
                    font-weight: 500;
                }}
                .btn {{
                    display: block;
                    background: linear-gradient(135deg, #EF7F1F 0%, #FF9D42 100%);
                    color: white !important;
                    text-decoration: none;
                    padding: 18px;
                    border-radius: 24px;
                    font-size: 16px;
                    font-weight: 800;
                    box-shadow: 0 15px 30px rgba(239, 127, 31, 0.25);
                    transition: all 0.3s ease;
                }}
                .btn:hover {{
                    transform: translateY(-2px);
                    box-shadow: 0 18px 35px rgba(239, 127, 31, 0.35);
                }}
                .btn:active {{
                    transform: translateY(1px);
                }}
            </style>
        </head>
        <body>
            <div class="orb-1"></div>
            <div class="orb-2"></div>
            <div class="pattern"></div>
            
            <div class="container">
                <div class="logo-wrapper">
                    <img class="logo-img" src="https://lh3.googleusercontent.com/d/1z4l9PuXoNFcJfwLTZn-D7zWq4ALjjxcf" alt="GenKiddo">
                </div>
                
                <div class="card">
                    <div class="error-icon-wrapper">
                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </div>
                    
                    <h1>Verifikasi Gagal!</h1>
                    <p>Token verifikasi tidak valid atau telah kedaluwarsa. Silakan lakukan pendaftaran ulang atau ajukan pengiriman ulang email verifikasi melalui aplikasi.</p>
                    
                    <a class="btn" href="{settings.FRONTEND_URL}/login">Kembali ke Halaman Login</a>
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)
    
    parent = res.data[0]
    # Mark parent as verified
    supabase.table("parents").update({"is_verified": True, "verification_token": None}).eq("id", parent["id"]).execute()
    
    # Redirect to parent dashboard or show successful HTML response
    from fastapi.responses import HTMLResponse
    html_content = f"""
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verifikasi Berhasil - GenKiddo Academy</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800;900&display=swap" rel="stylesheet">
        <style>
            body {{
                font-family: 'Poppins', sans-serif;
                background-color: #FFFAF5;
                margin: 0;
                padding: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                overflow: hidden;
                position: relative;
            }}
            .orb-1 {{
                position: absolute;
                top: 0;
                left: 0;
                width: 400px;
                height: 400px;
                background: #EF7F1F;
                opacity: 0.04;
                border-radius: 50%;
                transform: translate(-30%, -30%);
                filter: blur(80px);
                z-index: 1;
            }}
            .orb-2 {{
                position: absolute;
                bottom: 0;
                right: 0;
                width: 500px;
                height: 500px;
                background: #4EA8DE;
                opacity: 0.04;
                border-radius: 50%;
                transform: translate(30%, 30%);
                filter: blur(90px);
                z-index: 1;
            }}
            .pattern {{
                position: absolute;
                inset: 0;
                opacity: 0.2;
                background-image: radial-gradient(#EF7F1F 0.5px, transparent 0.5px);
                background-size: 24px 24px;
                z-index: 1;
            }}
            .container {{
                position: relative;
                z-index: 10;
                width: 90%;
                max-width: 500px;
                text-align: center;
                padding: 20px 0;
            }}
            .logo-wrapper {{
                background: white;
                padding: 18px;
                border-radius: 28px;
                box-shadow: 0 15px 35px rgba(239, 127, 31, 0.1);
                display: inline-block;
                margin-bottom: 30px;
            }}
            .logo-img {{
                height: 55px;
                display: block;
            }}
            .card {{
                background: white;
                border-radius: 36px;
                padding: 45px 35px;
                box-shadow: 0 25px 60px -15px rgba(239, 127, 31, 0.12);
                border: 1px solid rgba(239, 127, 31, 0.05);
            }}
            .success-icon-wrapper {{
                width: 80px;
                height: 80px;
                border-radius: 50%;
                background: #ECFDF5;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 25px auto;
                color: #10B981;
                box-shadow: 0 10px 20px rgba(16, 185, 129, 0.1);
            }}
            h1 {{
                color: #1F1F1F;
                font-size: 26px;
                font-weight: 900;
                margin: 0 0 15px 0;
                letter-spacing: -0.5px;
            }}
            p {{
                color: #666;
                font-size: 14px;
                line-height: 1.7;
                margin: 0 0 35px 0;
                font-weight: 500;
            }}
            .btn {{
                display: block;
                background: linear-gradient(135deg, #EF7F1F 0%, #FF9D42 100%);
                color: white !important;
                text-decoration: none;
                padding: 18px;
                border-radius: 24px;
                font-size: 16px;
                font-weight: 800;
                box-shadow: 0 15px 30px rgba(239, 127, 31, 0.25);
                transition: all 0.3s ease;
            }}
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 18px 35px rgba(239, 127, 31, 0.35);
            }}
            .btn:active {{
                transform: translateY(1px);
            }}
        </style>
    </head>
    <body>
        <div class="orb-1"></div>
        <div class="orb-2"></div>
        <div class="pattern"></div>
        
        <div class="container">
            <div class="logo-wrapper">
                <img class="logo-img" src="https://lh3.googleusercontent.com/d/1z4l9PuXoNFcJfwLTZn-D7zWq4ALjjxcf" alt="GenKiddo">
            </div>
            
            <div class="card">
                <div class="success-icon-wrapper">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                </div>
                
                <h1>Email Berhasil Diverifikasi!</h1>
                <p>Selamat Ayah & Bunda! Akun GenKiddo Academy Anda telah aktif sepenuhnya. Silakan kembali ke aplikasi dan login untuk mulai mendaftarkan kelas si kecil.</p>
                
                <a class="btn" href="{settings.FRONTEND_URL}/login?verified=true">Masuk ke Akun</a>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router.post("/resend-verification")
async def resend_verification(body: ResendVerificationRequest, background_tasks: BackgroundTasks):
    res = supabase.table("parents").select("*").eq("email", _normalize_email(body.email)).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email tidak terdaftar"
        )
    
    parent = res.data[0]
    if parent.get("is_verified"):
        return {"message": "Email sudah terverifikasi"}
        
    new_token = secrets.token_hex(20)
    supabase.table("parents").update({"verification_token": new_token}).eq("id", parent["id"]).execute()
    
    # Simulate sending email by printing verification URL
    verification_url = f"{settings.BACKEND_URL}/api/v1/auth/verify-email?token={new_token}"
    
    # Send HTML verification email via SMTP in background
    html_content = VERIFICATION_EMAIL_TEMPLATE.replace("{verification_url}", verification_url)
    background_tasks.add_task(
        send_html_email,
        to_email=str(body.email),
        subject="Verifikasi Akun GenKiddo Anda",
        html_content=html_content
    )
    
    print(f"\n[EMAIL SIMULATION] Verification email resent to {parent['email']}:\nLink: {verification_url}\n")
    
    return {"message": "Email verifikasi telah dikirim ulang."}


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    if "@" in req.email:
        email = _normalize_email(req.email)
        res = supabase.table("parents").select("*").eq("email", email).execute()
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email atau password salah"
            )
 
        parent = res.data[0]
        if parent.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun Anda telah dinonaktifkan oleh Admin."
            )
        if parent.get("role") == "mentor":
            mentor_res = supabase.table("mentors").select("is_active").eq("parent_id", parent["id"]).execute()
            mentor_profile = mentor_res.data[0] if mentor_res.data else None
            if mentor_profile and mentor_profile.get("is_active") is False:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Akun Anda telah dinonaktifkan oleh Admin."
                )
        stored_hash = parent.get("password_hash")
        if not stored_hash or not verify_password(req.password, stored_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email atau password salah"
            )
 
        access_token = create_access_token(
            data={"sub": parent["email"], "role": parent.get("role", "parent")},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
 
        user = UserResponse(
            id=parent["id"],
            name=parent["name"],
            email=parent["email"],
            whatsapp_number=parent.get("whatsapp_number", ""),
            city=parent.get("city", ""),
            role=parent.get("role", "parent"),
            is_verified=parent.get("is_verified", False),
            created_at=str(parent.get("created_at", "")) if parent.get("created_at") else None,
        )
    else:
        res = supabase.table("students").select("*").eq("username", str(req.email)).execute()
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Username atau password salah"
            )
 
        student = res.data[0]
        if student.get("status") == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun Anda telah dinonaktifkan oleh Admin."
            )
        if student.get("status") == "archived":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akun Anda sudah diarsipkan dan tidak dapat digunakan lagi."
            )
        stored_hash = student.get("password_hash")
        if not stored_hash or not verify_password(req.password, stored_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Username atau password salah"
            )
 
        access_token = create_access_token(
            data={"sub": student["id"], "role": "student"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
 
        user = UserResponse(
            id=student["id"],
            name=student["name"],
            username=student["username"],
            role="student",
            is_verified=True,  # Student bypasses verification checks
            created_at=str(student.get("created_at", "")) if student.get("created_at") else None,
        )
 
    return LoginResponse(access_token=access_token, user=user)
 
 
@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        name=current_user["name"],
        email=current_user.get("email"),
        username=current_user.get("username"),
        whatsapp_number=current_user.get("whatsapp_number", ""),
        city=current_user.get("city", ""),
        role=current_user.get("role", "parent"),
        is_verified=current_user.get("is_verified", False) if current_user.get("role") == "parent" else True,
        created_at=str(current_user.get("created_at", "")) if current_user.get("created_at") else None,
    )


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, background_tasks: BackgroundTasks):
    res = supabase.table("parents").select("*").eq("email", _normalize_email(body.email)).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email tidak terdaftar"
        )
    
    parent = res.data[0]
    reset_token = secrets.token_hex(20)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    
    supabase.table("parents").update({
        "reset_token": reset_token,
        "reset_expires_at": expires_at
    }).eq("id", parent["id"]).execute()
    
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
    
    # Send Reset HTML email via SMTP in background
    html_content = RESET_PASSWORD_EMAIL_TEMPLATE.replace("{reset_url}", reset_url)
    background_tasks.add_task(
        send_html_email,
        to_email=str(body.email),
        subject="Atur Ulang Password GenKiddo Anda",
        html_content=html_content
    )
    
    print(f"\n[EMAIL SIMULATION] Reset password email sent to {body.email}:\nLink: {reset_url}\n")
    
    return {"message": "Email atur ulang password telah dikirim."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    res = supabase.table("parents").select("*").eq("reset_token", body.token).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token atur ulang password tidak valid atau telah kedaluwarsa."
        )
    
    parent = res.data[0]
    expires_raw = parent.get("reset_expires_at")
    
    if expires_raw:
        if isinstance(expires_raw, str):
            expires_at = datetime.fromisoformat(expires_raw.replace('Z', '+00:00'))
        else:
            expires_at = expires_raw
            
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token atur ulang password telah kedaluwarsa."
            )
            
    # Hash new password and update
    new_hash = get_password_hash(body.password)
    supabase.table("parents").update({
        "password_hash": new_hash,
        "reset_token": None,
        "reset_expires_at": None
    }).eq("id", parent["id"]).execute()
    
    return {"message": "Password berhasil diatur ulang. Silakan login kembali."}

