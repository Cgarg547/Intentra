import os
import logging
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

TRUSTED_ORIGINS = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}


def _trusted_origins() -> set[str]:
    configured = os.getenv("INTENTRA_ALLOWED_ORIGINS", "")
    return TRUSTED_ORIGINS | {origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
logger = logging.getLogger(__name__)
CORRELATION_HEADER = "X-Intentra-Correlation-ID"
LEGACY_CORRELATION_HEADER = "X-Correlation-ID"


def _correlation_id(value: str | None) -> str:
    if value:
        try:
            return str(uuid.UUID(value))
        except (ValueError, AttributeError):
            pass
    return str(uuid.uuid4())


class OriginProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Prefer the namespaced header used by payment routes, while preserving
        # the proposal endpoint's established client correlation contract.
        legacy_correlation_id = request.headers.get(LEGACY_CORRELATION_HEADER)
        correlation_id = _correlation_id(
            request.headers.get(CORRELATION_HEADER) or legacy_correlation_id
        )
        request.state.correlation_id = correlation_id
        if request.method not in SAFE_METHODS:
            origin = request.headers.get("origin")
            fetch_site = request.headers.get("sec-fetch-site")

            if origin is not None and origin.rstrip("/") not in _trusted_origins():
                code = "ORIGIN_REJECTED"
                logger.warning("request_rejected", extra={
                    "event_name": "request_rejected",
                    "error_code": code,
                    "correlation_id": correlation_id,
                })
                return JSONResponse(
                    status_code=403,
                    content={"code": code, "detail": "Untrusted request origin"},
                    headers={"X-Intentra-Error-Code": code, CORRELATION_HEADER: correlation_id},
                )

            if fetch_site == "cross-site":
                code = "ORIGIN_REJECTED"
                logger.warning("request_rejected", extra={
                    "event_name": "request_rejected",
                    "error_code": code,
                    "correlation_id": correlation_id,
                })
                return JSONResponse(
                    status_code=403,
                    content={"code": code, "detail": "Cross-site request rejected"},
                    headers={"X-Intentra-Error-Code": code, CORRELATION_HEADER: correlation_id},
                )

        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        if legacy_correlation_id is not None:
            response.headers[LEGACY_CORRELATION_HEADER] = correlation_id
        return response
