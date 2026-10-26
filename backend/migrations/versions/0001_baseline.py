"""Baseline: db/schema.sql, the drug-family seed and the roles.

Revision ID: 0001
Revises:

The pre-hackathon design (D-25) lives in db/schema.sql. docker-compose loads it on first start, so on a database
that already has it this migration only records the baseline. On an empty database it loads the three files.
"""
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DB_DIR = Path(__file__).resolve().parents[3] / "db"


def _script(name: str) -> str:
    sql = (DB_DIR / name).read_text(encoding="utf-8")
    # Alembic owns the transaction.
    return "\n".join(l for l in sql.splitlines() if l.strip().upper() not in ("BEGIN;", "COMMIT;"))


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(sa.text("SELECT to_regclass('public.users') IS NOT NULL")).scalar()
    if exists:
        return
    for name in ("schema.sql", "seed_drug_families.sql", "roles_and_grants.sql"):
        conn.exec_driver_sql(_script(name).replace("%", "%%"))


def downgrade() -> None:
    raise RuntimeError("The baseline is not reversible. Drop the database instead.")
