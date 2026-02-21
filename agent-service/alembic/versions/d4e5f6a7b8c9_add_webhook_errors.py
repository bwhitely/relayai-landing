"""add webhook_errors table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'webhook_errors',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=True),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('error_type', sa.String(100), nullable=False),
        sa.Column('error_message', sa.Text, nullable=False),
        sa.Column('sender_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_webhook_errors_tenant_id', 'webhook_errors', ['tenant_id'])
    op.create_index('ix_webhook_errors_created_at', 'webhook_errors', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_webhook_errors_created_at', 'webhook_errors')
    op.drop_index('ix_webhook_errors_tenant_id', 'webhook_errors')
    op.drop_table('webhook_errors')
