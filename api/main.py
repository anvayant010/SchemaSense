from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.routes import router

app = FastAPI(
    title="SchemaSense API",
    description=(
        "Intelligent database schema analysis and suitability scoring. "
        "Upload a schema (CSV, SQL, JSON) and get compatibility scores, "
        "migration warnings, and AI-powered explanations for 12 databases."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not settings.is_production else [
        "https://schema-sense-tool.vercel.app/"
        # Add your actual Vercel URL here after deployment
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router, prefix="/api/v1")

@app.on_event("startup")
async def startup_checks():
    print(f"\n{'='*50}")
    print("SchemaSense API starting...")
    print(f"  Environment : {settings.environment}")
    print(f"  AI enabled  : {settings.has_ai}")
    print(f"  Async mode  : {settings.use_celery}")
    print(f"  DB features : {settings.db_features_path}")
    if not Path(settings.db_features_path).exists():
        print(f"  WARNING: db_features.json not found at {settings.db_features_path}")
    if not settings.has_ai:
        print("  NOTE: Set ANTHROPIC_API_KEY in .env to enable AI explanations")
    print(f"{'='*50}\n")


@app.get("/")
async def root():
    return {
        "name": "SchemaSense API",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/v1/health",
            "analyze": "POST /api/v1/analyze",
            "results": "GET /api/v1/results/{job_id}",
            "databases": "GET /api/v1/databases",
        }
    }