"""FastAPI application. Base path /api/v1 (docs/15-api-spec.md)."""
from __future__ import annotations

import secrets
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .api import agent, assist, auth, cards, checkins, tasks, demo, doctor, labels, members, outcomes, patients, plan, readings, tracking, trust, visits
from .services.errors import ServiceError
from .config import get_settings, production_problems
from .db import engine_app

app = FastAPI(title="CareSaathi API", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

s = get_settings()
_problems = production_problems(s)
if _problems:
    raise RuntimeError("Refusing to start with development settings on a public address:\n - " + "\n - ".join(_problems))
app.add_middleware(
    CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-Id"],
)


# The API answers with JSON and nothing else, so it may forbid everything (D-64). The interactive docs page is the one exception:
# it loads Swagger UI from a CDN, so it gets its own policy rather than weakening the policy that covers patient data.
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
_DOCS_CSP = ("default-src 'none'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' https://cdn.jsdelivr.net "
             "'unsafe-inline'; img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")


# A deployment that is live but not yet shown to anyone (D-69). While SITE_GATE_TOKEN is set, the only way in is the matching header,
# which the website adds server-side; nothing reaches a route, a database connection or the model without it. The answer is 404 rather
# than 403 so a crawler that finds the address learns nothing from it. The health paths stay open: the host checks them to know the
# container is alive, and they read nothing. Unset the variable on both ends and the gate is gone -- see PUBLIC_LAUNCH.md.
_GATE_OPEN = ("/healthz", "/readyz")


@app.middleware("http")
async def site_gate(request: Request, call_next):
    want = get_settings().site_gate_token
    if want and request.url.path not in _GATE_OPEN:
        got = request.headers.get("x-site-gate") or ""
        if not secrets.compare_digest(got, want):
            return JSONResponse({"detail": "Not found"}, status_code=404)
    return await call_next(request)


@app.middleware("http")
async def request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = rid
    resp = await call_next(request)
    resp.headers["X-Request-Id"] = rid
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    resp.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=(), payment=(), usb=()")
    resp.headers.setdefault("Content-Security-Policy", _DOCS_CSP if request.url.path.startswith("/api/docs") else _API_CSP)
    if s.public_base_url.startswith("https"):      # only where TLS is actually terminated, so local development still works over http
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
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
app.include_router(trust.router, prefix="/api/v1")
app.include_router(doctor.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(labels.router, prefix="/api/v1")
app.include_router(outcomes.router, prefix="/api/v1")
app.include_router(readings.router, prefix="/api/v1")
app.include_router(checkins.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    with engine_app().connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ready"}
