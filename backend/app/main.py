"""FinTrace FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Environment:
    Copy .env.example to .env (repository root) and fill in values.
    Leave DATABASE_URL empty to use the auto-created local SQLite file.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    action_router,
    audit_router,
    benchmark_router,
    dashboard_router,
    exceptions_router,
    investigate_router,
    investigation_router,
    lifecycle_router,
    reconciliation_router,
    transactions_router,
    verify_router,
)
from app.core.config import get_settings
from app.core.database import init_db

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create database tables on startup."""
    logger.info("FinTrace starting up (env=%s)…", settings.app_env)
    init_db()
    logger.info("Database tables ensured.")
    yield
    logger.info("FinTrace shutting down.")


app = FastAPI(
    title="FinTrace",
    description=(
        "AI-powered financial reconciliation and exception management API.\n\n"
        "Investigation flow: DETECTED → INVESTIGATE → EVIDENCE → ROOT CAUSE → "
        "IMPACT → RECOMMEND → CONTROLLER ACTION → VERIFY"
    ),
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env in ("local", "dev") else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
PREFIX = settings.api_prefix  # default: /api

app.include_router(dashboard_router, prefix=PREFIX)
app.include_router(exceptions_router, prefix=PREFIX)

# Investigation layer (new exception-scoped routes)
app.include_router(investigate_router, prefix=PREFIX)   # POST /api/exceptions/{id}/investigate
app.include_router(action_router, prefix=PREFIX)        # POST /api/exceptions/{id}/action
app.include_router(verify_router, prefix=PREFIX)        # POST /api/exceptions/{id}/verify

# Legacy investigation endpoint (kept for backwards compat)
app.include_router(investigation_router, prefix=PREFIX)

app.include_router(reconciliation_router, prefix=PREFIX)
app.include_router(benchmark_router, prefix=PREFIX)
app.include_router(transactions_router, prefix=PREFIX)
app.include_router(lifecycle_router, prefix=PREFIX)     # GET /api/transactions/{id}/trace
app.include_router(audit_router, prefix=PREFIX)         # GET /api/audit/{txn_id}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok", "app": settings.app_name, "env": settings.app_env})


@app.get("/", tags=["health"])
def root() -> JSONResponse:
    return JSONResponse(
        {
            "app": settings.app_name,
            "version": "1.1.0",
            "docs": "/docs",
            "health": "/health",
        }
    )
