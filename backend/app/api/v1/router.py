from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, organizations, users
from app.modules.breach_monitor.router import router as breach_router

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(breach_router, prefix="/breach", tags=["breach"])
