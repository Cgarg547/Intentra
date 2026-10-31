from intentra.middleware.origin import OriginProtectionMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from intentra.routes.auth import router as auth_router

app = FastAPI(
    title="INTENTRA API",
    version="0.1.0",
    description="AI Payment Intent Firewall",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.add_middleware(OriginProtectionMiddleware)
app.include_router(auth_router)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "intentra-api",
        "version": "0.1.0",
    }
