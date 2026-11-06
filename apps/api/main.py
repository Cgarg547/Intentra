import os
from intentra.routes.payments import router as payments_router
from intentra.routes.contracts import router as contracts_router
from intentra.middleware.origin import OriginProtectionMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from intentra.routes.auth import router as auth_router
from intentra.routes.agents import router as agents_router
from intentra.routes.workspace import router as workspace_router

app = FastAPI(
    title="INTENTRA API",
    version="0.1.0",
    description="AI Payment Intent Firewall",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "INTENTRA_CORS_ORIGINS",
            "http://localhost:3000",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.add_middleware(OriginProtectionMiddleware)
app.include_router(auth_router)
app.include_router(contracts_router)
app.include_router(payments_router)
app.include_router(agents_router)
app.include_router(workspace_router)

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "intentra-api",
        "version": "0.1.0",
    }
