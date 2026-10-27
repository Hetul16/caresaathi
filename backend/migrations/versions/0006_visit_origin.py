"""Mark where a visit came from.

Revision ID: 0006
Revises: 0005

A visit is either a real recording or a MOCK visit that replays a scripted synthetic conversation (for demos and tests when
no audio exists). The two are kept apart so a mock can never be mistaken for a real consultation on screen.
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE visits ADD COLUMN origin text NOT NULL DEFAULT 'recording' CHECK (origin IN ('recording', 'mock'));
    ALTER TABLE visits ADD COLUMN failure_note text;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE visits DROP COLUMN failure_note; ALTER TABLE visits DROP COLUMN origin;")
