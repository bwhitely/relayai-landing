"""add scheduled_jobs table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-21 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scheduled_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('cron_expression', sa.String(100), nullable=False),
        sa.Column('prompt', sa.Text, nullable=False),
        sa.Column('delivery_channel',
                  sa.Enum('email', 'slack', 'none', name='deliverychannel'),
                  nullable=False, server_default='none'),
        sa.Column('delivery_target', sa.Text, nullable=True),
        sa.Column('enabled', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scheduled_jobs_tenant_id', 'scheduled_jobs', ['tenant_id'])
    op.create_index('ix_scheduled_jobs_enabled', 'scheduled_jobs', ['enabled'])


def downgrade() -> None:
    op.drop_index('ix_scheduled_jobs_enabled', 'scheduled_jobs')
    op.drop_index('ix_scheduled_jobs_tenant_id', 'scheduled_jobs')
    op.drop_table('scheduled_jobs')
    op.execute("DROP TYPE IF EXISTS deliverychannel")
