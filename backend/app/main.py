"""FastAPI application. Base path /api/v1 (docs/15-api-spec.md)."""
from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .api import assist, auth, cards, demo, members, patients, plan, tracking, visits
from .services.errors import ServiceError
from .config import get_settings
from .db import engine_app

app = FastAPI(title="CareSaathi API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

s = get_settings()
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-Id"],
)


@app.middleware("http")
async def request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = rid
    resp = await call_next(request)
    resp.headers["X-Request-Id"] = rid
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


def _problem(request: Request, status: int, type_: str, title: str, detail: str = "", errors: list | None = None):
    return JSONResponse(
        {"type": f"https://caresaathi.example/problems/{type_}", "title": title, "status": status, "detail": detail,
         "request_id": getattr(request.state, "request_id", None), "errors": errors or []},
        status_code=status, media_type="application/problem+json")


@app.exception_handler(HTTPException)
async def http_exc(request: Request, exc: HTTPException):
    d = exc.detail if isinstance(exc.detail, dict) else {"type": "error", "title": str(exc.detail), "detail": ""}
    return _problem(request, exc.status_code, d.get("type", "error"), d.get("title", ""), d.get("detail", ""))


@app.exception_handler(ServiceError)
async def service_exc(request: Request, exc: ServiceError):
    return _problem(request, exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_exc(request: Request, exc: RequestValidationError):
    errs = [{"field": ".".join(str(x) for x in e["loc"][1:]), "message": e["msg"].removeprefix("Value error, ")} for e in exc.errors()]
    return _problem(request, 422, "validation-failed", "Please check the highlighted fields", errors=errs)


app.include_router(auth.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(plan.router, prefix="/api/v1")
app.include_router(cards.router, prefix="/api/v1")
app.include_router(tracking.router, prefix="/api/v1")
app.include_router(visits.router, prefix="/api/v1")
app.include_router(demo.router, prefix="/api/v1")
app.include_router(members.router, prefix="/api/v1")
app.include_router(assist.router, prefix="/api/v1")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    with engine_app().connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ready"}
