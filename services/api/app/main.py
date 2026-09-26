"""Tremor Retail API. Run: uvicorn app.main:app --reload --port 8000 (from services/api)."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException

from . import config
from .api import reviews, runs, signals
from .api.errors import http_error, unexpected_error, validation_error
from .models.responses import ErrorResponse
from .pipeline import llm

app = FastAPI(
    title="Tremor Retail API",
    version="1.1.0",
    # Explicit labels keep OpenAPI stable across Python's HTTPStatus wording changes.
    responses={
        code: {"model": ErrorResponse, "description": description}
        for code, description in {
            400: "Bad Request",
            404: "Not Found",
            409: "Conflict",
            413: "Content Too Large",
            422: "Unprocessable Content",
            500: "Internal Server Error",
        }.items()
    },
    description="Evidence-backed profit leakage signals for small grocery retailers. "
    "Investigation leads only; no automatic actions.",
)
app.add_exception_handler(HTTPException, http_error)
app.add_exception_handler(RequestValidationError, validation_error)
app.add_exception_handler(Exception, unexpected_error)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(runs.router)
app.include_router(signals.router)
app.include_router(reviews.router)


@app.get("/api/health")
def health():
    return {"ok": True, "llm_enabled": llm.enabled(), "model": llm.model_name(), "detector_version": config.DETECTOR_VERSION}
