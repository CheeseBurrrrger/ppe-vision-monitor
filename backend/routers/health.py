from fastapi import APIRouter
from config import settings
from database import get_pool
from schemas import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API and database connectivity."""
    db_status = "healthy"
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        db_status = "unhealthy"

    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        database=db_status,
    )