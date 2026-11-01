"""Persist bounded conversational interviews and idempotent turns."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261029_0006'
down_revision = '20261026_0005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('interview_sessions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('repository_id', sa.Uuid(), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('commit_sha', sa.String(64), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('max_turns', sa.Integer(), nullable=False),
        sa.Column('initial_request', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'finished')", name=op.f('ck_interview_sessions_interview_status_valid')),
        sa.CheckConstraint('version >= 0 AND version <= max_turns AND max_turns BETWEEN 1 AND 20',
                           name=op.f('ck_interview_sessions_interview_progress_valid')),
    )
    op.create_index('ix_interview_sessions_repository_id', 'interview_sessions', ['repository_id'])
    op.create_table('interview_turns',
        sa.Column('session_id', sa.Uuid(), sa.ForeignKey('interview_sessions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('sequence', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.Uuid(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('response', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('session_id', 'request_id', name='uq_interview_turns_request'),
        sa.CheckConstraint('sequence BETWEEN 0 AND 20', name=op.f('ck_interview_turns_interview_turn_sequence_valid')),
    )


def downgrade():
    op.drop_table('interview_turns')
    op.drop_table('interview_sessions')
