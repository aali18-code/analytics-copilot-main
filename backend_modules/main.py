"""FastAPI entry point for the new React frontend."""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_modules.auth import require_auth, router as auth_router
from backend_modules.ask_ai.api import router as ask_ai_router
from backend_modules.dashboard.api import router as dashboard_router
from backend_modules.llm_monitoring.api import router as monitoring_router

app = FastAPI(title="Analytics Copilot API")


@app.middleware("http")
async def no_store_api_responses(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

origins = [origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type"])

app.include_router(auth_router)
app.include_router(dashboard_router, dependencies=[Depends(require_auth)])
app.include_router(ask_ai_router, dependencies=[Depends(require_auth)])
app.include_router(monitoring_router, dependencies=[Depends(require_auth)])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
