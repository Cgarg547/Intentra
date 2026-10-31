from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="INTENTRA API",
    version="0.1.0",
    description="AI Payment Intent Firewall",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "intentra-api",
        "version": "0.1.0",
    }
