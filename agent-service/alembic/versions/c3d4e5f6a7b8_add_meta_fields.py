"""add meta_page_id and meta_credentials to tenants

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column(
        'meta_page_id',
        sa.String(64),
        nullable=True,
        unique=True,
    ))
    op.add_column('tenants', sa.Column(
        'meta_credentials',
        sa.Text(),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('tenants', 'meta_credentials')
    op.drop_column('tenants', 'meta_page_id')
