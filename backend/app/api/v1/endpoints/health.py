from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> dict:
    """Health check endpoint for load balancers and container orchestrators."""
    return {
        "status": "ok",
        "service": "corvin-api",
        "version": "0.1.0",
    }
