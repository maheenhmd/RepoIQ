"""Prepare 768-dimensional code embeddings without discarding prior vectors."""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "20261026_0005"
down_revision = "20261026_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("LOCK TABLE code_chunks IN ACCESS EXCLUSIVE MODE")
    op.add_column("code_chunks", sa.Column("legacy_embedding", Vector(), nullable=True))
    op.add_column("code_chunks", sa.Column("embedding_model", sa.Text(), nullable=True))
    op.execute("UPDATE code_chunks SET legacy_embedding = embedding WHERE embedding IS NOT NULL")
    # Old vectors belong to an unknown model; retain them but regenerate active vectors.
    op.alter_column("code_chunks", "embedding", type_=Vector(768),
                    postgresql_using="NULL::vector(768)", existing_nullable=True)


def downgrade() -> None:
    # Refuse data loss rather than silently dropping newly generated embeddings.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM code_chunks WHERE embedding IS NOT NULL
                   OR (legacy_embedding IS NOT NULL AND vector_dims(legacy_embedding) <> 384)) THEN
            RAISE EXCEPTION 'Export active/non-384 vectors before downgrade';
        END IF;
    END $$""")
    op.alter_column("code_chunks", "embedding", type_=Vector(384),
                    postgresql_using="legacy_embedding::vector(384)", existing_nullable=True)
    op.drop_column("code_chunks", "embedding_model")
    op.drop_column("code_chunks", "legacy_embedding")
