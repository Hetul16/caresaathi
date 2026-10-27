"""Keep the model's draft beside what was shown, for the trust panel.

Revision ID: 0007
Revises: 0006

generated_outputs.body is what the family may see (the guard's fallback when a draft was blocked). draft_text is what the model
wrote, and guard_report says what the guard found. Both are read-only evidence; nothing reads draft_text back into the product.
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE generated_outputs ADD COLUMN draft_text text;
    ALTER TABLE generated_outputs ADD COLUMN guard_report jsonb NOT NULL DEFAULT '{}'::jsonb;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE generated_outputs DROP COLUMN guard_report; ALTER TABLE generated_outputs DROP COLUMN draft_text;")
