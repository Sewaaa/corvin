import re
import time
import uuid
from typing import Callable, Optional

import structlog
from fastapi import Request, Response
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Patterns for masking sensitive data in logs
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
TOKEN_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*")


def _mask_sensitive(value: str) -> str:
    """Mask emails and Bearer tokens in log strings."""
    value = EMAIL_PATTERN.sub("[EMAIL REDACTED]", value)
    value = TOKEN_PATTERN.sub("Bearer [TOKEN REDACTED]", value)
    return value


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured request/response logging middleware.
    Logs method, path, status code, and duration.
    Sensitive data (emails, tokens) is masked before logging.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # Bind request context for structured logging
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=_mask_sensitive(str(request.url.path)),
        )

        # Add request ID to response headers
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "http_request",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Extracts the organization_id from the JWT and attaches it to
    request.state so that all downstream handlers can scope queries
    to the correct tenant without trusting user-supplied org IDs.

    Public routes (auth endpoints, health check) are skipped.
    """

    PUBLIC_PATHS = {
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request.state.organization_id = None
        request.state.user_id = None

        path = request.url.path

        # Skip public paths
        if path in self.PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]
            try:
                payload = jwt.decode(
                    token,
                    settings.secret_key,
                    algorithms=[settings.algorithm],
                )
                request.state.user_id = payload.get("sub")
                request.state.organization_id = payload.get("org_id")
            except JWTError:
                # Let the endpoint handle authentication errors
                pass

        return await call_next(request)
