"""Make full source content storage optional.

Revision ID: 20261026_0002
Revises: 20261026_0001
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261026_0002"
down_revision: str | None = "20261026_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "repository_files", "content", existing_type=sa.Text(), nullable=True
    )


def downgrade() -> None:
    # Restore genuine content for NULL rows before downgrading. PostgreSQL
    # rejects SET NOT NULL otherwise; never delete rows or invent source text.
    op.alter_column(
        "repository_files", "content", existing_type=sa.Text(), nullable=False
    )
