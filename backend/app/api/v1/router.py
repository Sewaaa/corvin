from fastapi import APIRouter

from app.api.v1.endpoints import audit, auth, health, organizations, users
from app.modules.breach_monitor.router import router as breach_router
from app.modules.domain_reputation.router import router as domain_router
from app.modules.web_scanner.router import router as web_scan_router
from app.modules.email_protection.router import router as email_router
from app.modules.sandbox.router import router as sandbox_router
from app.modules.notifications.router import router as notifications_router
from app.modules.reports.router import router as reports_router

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(breach_router, prefix="/breach", tags=["breach"])
api_router.include_router(domain_router, prefix="/domain", tags=["domain"])
api_router.include_router(web_scan_router, prefix="/web-scan", tags=["web-scan"])
api_router.include_router(email_router, prefix="/email", tags=["email"])
api_router.include_router(sandbox_router, prefix="/sandbox", tags=["sandbox"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
