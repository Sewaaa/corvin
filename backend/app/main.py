from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import engine, Base
from app.core.middleware import LoggingMiddleware, TenantIsolationMiddleware

limiter = Limiter(key_func=get_remote_address)

logger = structlog.get_logger(__name__)


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            __import__("logging").getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    configure_logging()
    logger.info("corvin_api_starting", environment=settings.environment)
    # In production, run migrations via alembic before startup, not here
    yield
    logger.info("corvin_api_shutdown")
    await engine.dispose()


app = FastAPI(
    title="Corvin API",
    description="Silent guardian for your digital perimeter.",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_tags=[
        {"name": "auth", "description": "Authentication and MFA"},
        {"name": "organizations", "description": "Organization management"},
        {"name": "breach", "description": "Breach monitoring via HIBP"},
        {"name": "domain", "description": "Domain reputation and DNS health"},
        {"name": "web-scan", "description": "Passive web vulnerability scanning"},
        {"name": "sandbox", "description": "File static analysis sandbox"},
        {"name": "email-protection", "description": "Email threat detection"},
        {"name": "notifications", "description": "Alerts and notifications"},
        {"name": "reports", "description": "Executive PDF report + JSON summary aggregati"},
    ],
    lifespan=lifespan,
)

# Register rate limiter — slowapi reads app.state.limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Trusted hosts middleware (production hardening)
if settings.environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"],  # Configure with real hosts in production
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

# Structured request logging middleware
app.add_middleware(LoggingMiddleware)

# Tenant isolation middleware (reads JWT, sets org_id on request state)
app.add_middleware(TenantIsolationMiddleware)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint for load balancers and container orchestrators."""
    return {"status": "healthy", "service": "corvin-api"}
