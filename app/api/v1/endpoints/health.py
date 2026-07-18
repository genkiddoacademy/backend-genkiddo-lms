import time
from datetime import datetime, timezone
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.core.postgre import supabase

router = APIRouter(tags=["Health Check"])

# Record application start time
START_TIME = time.time()

@router.get("/health")
async def health_check():
    """
    GET /health — Basic liveness check.
    Returns status ok and current timestamp.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }

@router.get("/health/detailed")
async def health_detailed():
    """
    GET /health/detailed — Readiness check.
    Checks Supabase database connection and calculates uptime.
    Handles timeouts and database failures gracefully.
    """
    database_status = "error"
    
    try:
        # Check connectivity by querying a single row from the parents table
        # Since this executes via httpx.Client, we catch any connection/timeout errors
        res = supabase.table("parents").select("id").limit(1).execute()
        if res and hasattr(res, 'data'):
            database_status = "connected"
    except Exception as e:
        # Log the database connection error locally
        print(f"Healthcheck database connection error: {e}")
        database_status = "error"

    status_name = "ok" if database_status == "connected" else "degraded"
    status_code = status.HTTP_200_OK if status_name == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_name,
            "database": database_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": round(time.time() - START_TIME, 2)
        }
    )
