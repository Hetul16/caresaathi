"""Integration test harness.

The API tests run against a scratch database (caresaathi_test) cloned from the dev database's schema, grants,
policies and drug reference list, inside the same Postgres container. They never touch dev data. If Docker or the
container is not available the API tests are skipped, not failed; the report says how many were skipped.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[2]
TEST_DB = "caresaathi_test"
CONTAINER = os.environ.get("CARESAATHI_DB_CONTAINER", "caresaathi-db-1")


def _read_env() -> dict[str, str]:
    out: dict[str, str] = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


_ENV = _read_env()


def _point_at_scratch() -> None:
    for key in ("DATABASE_URL_APP", "DATABASE_URL_AUTH", "DATABASE_URL_WORKER", "DATABASE_URL_ADMIN"):
        url = _ENV.get(key)
        if url:
            os.environ[key] = url.rsplit("/", 1)[0] + "/" + TEST_DB
    for key in ("JWT_SECRET", "TOKEN_PEPPER"):
        if _ENV.get(key):
            os.environ[key] = _ENV[key]
    os.environ["MODEL_MODE"] = "fake"
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["LOCAL_STORAGE_DIR"] = tempfile.mkdtemp(prefix="caresaathi-test-storage-")
    os.environ["PUBLIC_BASE_URL"] = "http://localhost:3000"


_point_at_scratch()


def _docker(*args: str, stdin: str | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "exec", "-i", CONTAINER, *args], input=stdin, text=True, capture_output=True, timeout=timeout)


@pytest.fixture(scope="session")
def scratch_db():
    try:
        probe = _docker("psql", "-U", "postgres", "-d", "caresaathi", "-tAc", "select 1", timeout=30)
    except Exception as e:                                           # docker missing or not responding
        pytest.skip(f"database container not available: {e}")
    if probe.returncode != 0:
        pytest.skip("database container not available")
    steps = [
        ["psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
         f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)", "-c", f"CREATE DATABASE {TEST_DB}"],
        ["bash", "-c", f"pg_dump -U postgres -s caresaathi | psql -U postgres -q -d {TEST_DB} -v ON_ERROR_STOP=1"],
        ["bash", "-c", f"pg_dump -U postgres -a -t drug_families -t drug_substances -t drug_family_members -t reference_checks caresaathi"
                       f" | psql -U postgres -q -d {TEST_DB} -v ON_ERROR_STOP=1"],
    ]
    for cmd in steps:
        r = _docker(*cmd)
        if r.returncode != 0:
            pytest.fail(f"could not build the scratch database: {r.stderr[-500:]}")
    yield TEST_DB


@pytest.fixture(scope="session")
def admin(scratch_db):
    """A superuser connection to the scratch database, for arranging data that only the pipeline or a visit would create."""
    url = _ENV["DATABASE_URL_ADMIN"].replace("postgresql+psycopg", "postgresql").rsplit("/", 1)[0] + "/" + TEST_DB
    with psycopg.connect(url, autocommit=True) as c:
        yield c


@pytest.fixture(scope="session")
def client(scratch_db):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, base_url="http://localhost") as c:
        yield c


class Family:
    """A signed-in user, a patient they created, and helpers."""

    def __init__(self, client, admin, name: str = "Priya Kulkarni"):
        self.client, self.admin = client, admin
        self.email = f"t{uuid.uuid4().hex[:10]}@example.com"
        r = client.post("/api/v1/auth/register", json={"display_name": name, "email": self.email, "password": "correct-horse-battery"})
        assert r.status_code == 201, r.text
        self.user_id = r.json()["user"]["id"]
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = client.post("/api/v1/patients", headers=self.h, json={"full_name": "Ramesh Kulkarni", "preferred_language": "hi"})
        assert r.status_code == 201, r.text
        self.pid = r.json()["id"]

    def get(self, path, **kw):
        return self.client.get(f"/api/v1{path}", headers=self.h, **kw)

    def post(self, path, json=None, **kw):
        return self.client.post(f"/api/v1{path}", headers=self.h, json=json if json is not None else {}, **kw)

    def upload(self, text: str, name: str = "doc.txt", doc_type: str = "discharge_summary") -> str:
        r = self.client.post(f"/api/v1/patients/{self.pid}/documents", headers=self.h, data={"doc_type": doc_type},
                             files={"file": (name, text.encode(), "text/plain")})
        assert r.status_code == 202, r.text
        doc_id = r.json()["id"]
        for _ in range(100):
            d = self.client.get(f"/api/v1/documents/{doc_id}", headers=self.h).json()
            if d["status"] in ("extracted", "needs_review", "failed"):
                return doc_id
            time.sleep(0.1)
        raise AssertionError("document was not processed in time")

    def plan(self) -> dict:
        r = self.get(f"/patients/{self.pid}/care-plan")
        assert r.status_code == 200, r.text
        return r.json()

    def second_member(self, *, can_approve: bool) -> dict:
        """Another family member of the same patient, added directly (invitations are not built yet)."""
        email = f"m{uuid.uuid4().hex[:10]}@example.com"
        r = self.client.post("/api/v1/auth/register", json={"display_name": "Anil Kulkarni", "email": email, "password": "correct-horse-battery"})
        uid = r.json()["user"]["id"]
        self.admin.execute("""INSERT INTO family_members (patient_id, user_id, member_role, status, can_approve, can_manage_members)
                              VALUES (%s, %s, 'child', 'active', %s, false)""", (self.pid, uid, can_approve))
        return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(autouse=True)
def _no_signup_cap():
    """Every test signs up a fresh family from one address, which the real per-address cap on account creation would block after ten.
    The cap itself is exercised in test_ratelimit.py; here it is reset between tests so it does not limit the harness."""
    from app.safety.ratelimit import limiter
    limiter.clear("register_ip", "testclient")
    yield


@pytest.fixture
def family(client, admin):
    return Family(client, admin)


@pytest.fixture
def stranger(client, admin):
    return Family(client, admin, name="Someone Else")
