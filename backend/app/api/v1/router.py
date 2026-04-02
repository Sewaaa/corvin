from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, organizations, users
from app.modules.breach_monitor.router import router as breach_router
from app.modules.domain_reputation.router import router as domain_router
from app.modules.web_scanner.router import router as web_scan_router
from app.modules.email_protection.router import router as email_router

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(breach_router, prefix="/breach", tags=["breach"])
api_router.include_router(domain_router, prefix="/domain", tags=["domain"])
api_router.include_router(web_scan_router, prefix="/web-scan", tags=["web-scan"])
api_router.include_router(email_router, prefix="/email", tags=["email"])
