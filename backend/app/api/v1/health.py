import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.redis import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("", status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint to verify database and caching availability."""
    db_healthy = False
    redis_healthy = False
    errors = {}
    
    # 1. Test Database
    try:
        await db.execute(select(1))
        db_healthy = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        errors["database"] = str(e)
        
    # 2. Test Redis
    try:
        await redis_client.connect()
        if redis_client.client:
            await redis_client.client.ping()
            redis_healthy = True
        else:
            errors["redis"] = "Redis client not connected"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        errors["redis"] = str(e)

    health_status = {
        "status": "healthy" if db_healthy and redis_healthy else "unhealthy",
        "services": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy"
        }
    }

    if not db_healthy or not redis_healthy:
        health_status["errors"] = errors
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )

    return health_status
