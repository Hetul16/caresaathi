"""Database engines and the per-request context that row-level security relies on (docs/15-api-spec.md section 1).

One engine per role. The context (user, paired device or public card) is set with SET LOCAL inside the
transaction, so it can never leak between requests on a pooled connection. Keep this in ONE place.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from functools import lru_cache
from typing import Callable, Iterator
from uuid import UUID

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .config import get_settings


@lru_cache
def engine_app() -> Engine:
    return create_engine(get_settings().database_url_app, pool_pre_ping=True, pool_size=10)


@lru_cache
def engine_auth() -> Engine:
    return create_engine(get_settings().database_url_auth, pool_pre_ping=True, pool_size=5)


@lru_cache
def engine_worker() -> Engine:
    return create_engine(get_settings().database_url_worker, pool_pre_ping=True, pool_size=5)


def run_after_commit(session: Session, fn: Callable[[], None]) -> None:
    """Run fn on a background thread once this session's transaction has committed.
    A job that reads rows written in the same request must start here, never before the commit."""
    session.info.setdefault("after_commit", []).append(fn)


@event.listens_for(Session, "after_commit")
def _fire_after_commit(session: Session) -> None:
    for fn in session.info.pop("after_commit", []):
        threading.Thread(target=fn, daemon=True).start()


@event.listens_for(Session, "after_rollback")
def _drop_after_commit(session: Session) -> None:
    session.info.pop("after_commit", None)


def _set(session: Session, key: str, value: UUID | None) -> None:
    # set_config(..., is_local=true) is the parameter-safe form of SET LOCAL.
    session.execute(text("SELECT set_config(:k, :v, true)"), {"k": key, "v": str(value) if value else ""})


@contextmanager
def request_session(*, user_id: UUID | None = None, device_patient_id: UUID | None = None,
                    public_card_patient_id: UUID | None = None, engine: Engine | None = None) -> Iterator[Session]:
    """One transaction with the RLS context set. Commits on success, rolls back on error."""
    with Session(engine or engine_app()) as s, s.begin():
        _set(s, "app.user_id", user_id)
        _set(s, "app.device_patient_id", device_patient_id)
        _set(s, "app.public_card_patient_id", public_card_patient_id)
        yield s


@contextmanager
def auth_session() -> Iterator[Session]:
    """Login, registration and invitations: the `users` table only (caresaathi_auth role)."""
    with Session(engine_auth()) as s, s.begin():
        yield s


@contextmanager
def worker_session() -> Iterator[Session]:
    """Background jobs. Bypasses RLS; credentials never reach the web process in production."""
    with Session(engine_worker()) as s, s.begin():
        yield s
