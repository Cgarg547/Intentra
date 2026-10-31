from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

TRUSTED_ORIGINS = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class OriginProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in SAFE_METHODS:
            origin = request.headers.get("origin")
            fetch_site = request.headers.get("sec-fetch-site")

            if origin is not None and origin not in TRUSTED_ORIGINS:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Untrusted request origin"},
                )

            if fetch_site == "cross-site":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Cross-site request rejected"},
                )

        return await call_next(request)
