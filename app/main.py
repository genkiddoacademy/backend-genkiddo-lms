from fastapi import FastAPI, Depends, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException as FastAPIHTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
import os
import logging
from app.api.v1.endpoints import register, promo, auth, dashboard, admin, courses, quiz, lms, payments, health, mentor, shortlinks, users
from app.api.v1.endpoints.discovery_assessments import router as discovery_assessments_router
from app.api.deps import get_api_key
from app.core.config import settings

# Trigger reload for new GATEWAY_URL settings (v4)
# Disable default documentation URLs to secure them
app = FastAPI(
    title="GenKiddo Internal API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)


def _assert_discovery_routes_registered(target_app: FastAPI) -> None:
    expected_routes = {
        ("GET", "/api/v1/discovery-assessments"),
        ("POST", "/api/v1/discovery-assessments"),
        ("GET", "/api/v1/discovery-assessments/{assessment_id}"),
        ("PUT", "/api/v1/discovery-assessments/{assessment_id}"),
        ("DELETE", "/api/v1/discovery-assessments/{assessment_id}"),
        ("PATCH", "/api/v1/discovery-assessments/{assessment_id}/publish"),
        ("GET", "/api/v1/mentor/discovery-assessments"),
        ("POST", "/api/v1/mentor/discovery-assessments"),
        ("GET", "/api/v1/parent/discovery-assessments"),
        ("GET", "/api/v1/parent/discovery-assessments/{assessment_id}"),
    }
    registered_routes = {
        (method, getattr(route, "path", ""))
        for route in target_app.routes
        for method in getattr(route, "methods", set())
        if "discovery" in getattr(route, "path", "")
    }
    missing = sorted(expected_routes - registered_routes)
    if missing:
        logger = logging.getLogger("uvicorn.error")
        logger.warning("Discovery Assessment routes not fully registered: %s", missing)


# List of allowed origins for CORS
allowed_origins = [
    "https://genkiddo.id",
    "http://localhost:3000",
    "https://staging.genkiddo.id",
]

# Konfigurasi CORS: Lebih ketat untuk Production
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Ensure storage subdirectories exist
for folder in [
    "assignments/submissions", "assignments/tasks",
    "branding/course-banners", "branding/instructor-assets", "branding/thumbnails",
    "certificates/issued", "certificates/templates",
    "generated/analytics", "generated/quizzes", "generated/reports",
    "materials/attachments", "materials/courses", "materials/lessons", "materials/modules",
    "tmp/processing", "tmp/uploads",
    "users/avatars", "users/documents", "users/temp"
]:
    os.makedirs(os.path.join(settings.STORAGE_PATH, folder), exist_ok=True)

from fastapi import Response
from app.services.storage import storage_client

@app.get("/uploads/{bucket}/{path:path}")
async def serve_file(bucket: str, path: str):
    import mimetypes
    file_path = f"{bucket}/{path}"
    print(f"[DEBUG] Serving file from R2: {file_path}")
    content = storage_client.download_file(file_path)
    if not content:
        print(f"[DEBUG] File not found or error downloading from R2: {file_path}")
        raise HTTPException(status_code=404, detail="File tidak ditemukan")
        
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"
        
    return Response(content=content, media_type=mime_type)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print(f"Validation Error: {exc.errors()}")
    response = JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )
    return response

@app.exception_handler(FastAPIHTTPException)
async def fastapi_http_exception_handler(request, exc):
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
    return response

@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request, exc):
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    print(f"Global Error: {str(exc)}")
    traceback.print_exc()
    response = JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )
    return response


# Apply API Key dependency selectively
app.include_router(register.router, prefix="/api/v1", tags=["Pendaftaran"], dependencies=[Depends(get_api_key)])
app.include_router(promo.router, prefix="/api/v1/promo", tags=["Promo"], dependencies=[Depends(get_api_key)])
app.include_router(auth.router)
app.include_router(dashboard.router, dependencies=[Depends(get_api_key)])
app.include_router(admin.router, dependencies=[Depends(get_api_key)])
app.include_router(courses.router, prefix="/api/v1", dependencies=[Depends(get_api_key)])
app.include_router(quiz.admin_router, prefix="/api/v1", dependencies=[Depends(get_api_key)])
app.include_router(quiz.lms_router, prefix="/api/v1", dependencies=[Depends(get_api_key)])
app.include_router(lms.router, prefix="/api/v1", dependencies=[Depends(get_api_key)])
app.include_router(mentor.router, dependencies=[Depends(get_api_key)])
app.include_router(shortlinks.router, prefix="/api/v1", dependencies=[Depends(get_api_key)])
app.include_router(payments.router)
app.include_router(users.router, dependencies=[Depends(get_api_key)])
app.include_router(discovery_assessments_router, prefix="/api/v1", dependencies=[Depends(get_api_key)])
app.include_router(health.router)
_assert_discovery_routes_registered(app)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, error: str = None):
    auth_cookie = request.cookies.get("docs_auth")
    if auth_cookie == settings.ADMIN_PASSWORD:
        return RedirectResponse(url="/docs", status_code=303)

    error_placeholder = ""
    if error:
        error_placeholder = f"""
        <div class="error-alert">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <span>{error}</span>
        </div>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Akses API Docs - GenKiddo Academy</title>
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
                max-width: 450px;
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
                text-align: left;
            }}
            h1 {{
                color: #1F1F1F;
                font-size: 26px;
                font-weight: 900;
                margin: 0 0 10px 0;
                letter-spacing: -0.5px;
                text-align: center;
            }}
            p {{
                color: #666;
                font-size: 14px;
                line-height: 1.6;
                margin: 0 0 30px 0;
                font-weight: 500;
                text-align: center;
            }}
            .form-group {{
                margin-bottom: 25px;
            }}
            label {{
                display: block;
                font-weight: 800;
                color: #4A4A4A;
                font-size: 13px;
                margin-bottom: 8px;
                margin-left: 4px;
            }}
            input[type="password"] {{
                width: 100%;
                box-sizing: border-box;
                background-color: #F8F9FA;
                border: 1px solid #E2E8F0;
                padding: 18px 20px;
                border-radius: 20px;
                font-size: 16px;
                font-family: inherit;
                font-weight: 600;
                color: #1F1F1F;
                outline: none;
                transition: all 0.3s ease;
            }}
            input[type="password"]:focus {{
                background-color: white;
                border-color: #EF7F1F;
                box-shadow: 0 0 0 4px rgba(239, 127, 31, 0.1);
            }}
            .error-alert {{
                background-color: #FEF2F2;
                border: 1px solid #FEE2E2;
                color: #EF4444;
                padding: 15px 20px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 700;
                margin-bottom: 25px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .btn {{
                width: 100%;
                border: none;
                cursor: pointer;
                display: block;
                background: linear-gradient(135deg, #EF7F1F 0%, #FF9D42 100%);
                color: white;
                text-decoration: none;
                padding: 18px;
                border-radius: 24px;
                font-size: 16px;
                font-weight: 800;
                box-shadow: 0 15px 30px rgba(239, 127, 31, 0.25);
                transition: all 0.3s ease;
                text-align: center;
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
                <h1>Akses API Docs</h1>
                <p>Masukkan sandi administrator untuk mengakses dokumentasi FastAPI GenKiddo Academy.</p>
                
                {error_placeholder}
                
                <form method="POST" action="/admin-login">
                    <div class="form-group">
                        <label for="password">Kata Sandi Admin</label>
                        <input type="password" id="password" name="password" placeholder="••••••••" required autofocus>
                    </div>
                    <button type="submit" class="btn">Masuk Dokumentasi</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/admin-login")
async def admin_login(password: str = Form(...)):
    if password == settings.ADMIN_PASSWORD:
        response = RedirectResponse(url="/docs", status_code=303)
        response.set_cookie(key="docs_auth", value=password, max_age=86400, httponly=True)
        return response
    return RedirectResponse(url="/?error=Password+Admin+salah", status_code=303)

@app.get("/docs", include_in_schema=False)
async def get_swagger_documentation(request: Request):
    auth_cookie = request.cookies.get("docs_auth")
    if auth_cookie != settings.ADMIN_PASSWORD:
        return RedirectResponse(url="/", status_code=303)
    
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app.title + " - Swagger UI"
    )

@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(request: Request):
    auth_cookie = request.cookies.get("docs_auth")
    if auth_cookie != settings.ADMIN_PASSWORD:
        return RedirectResponse(url="/", status_code=303)
    
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=app.title + " - ReDoc"
    )

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint(request: Request):
    auth_cookie = request.cookies.get("docs_auth")
    if auth_cookie != settings.ADMIN_PASSWORD:
        return RedirectResponse(url="/", status_code=303)
    
    return get_openapi(title=app.title, version=app.version, routes=app.routes)
