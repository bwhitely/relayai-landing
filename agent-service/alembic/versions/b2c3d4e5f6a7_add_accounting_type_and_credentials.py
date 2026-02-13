"""add accounting_type and accounting_credentials

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    accountingtype = sa.Enum('xero', 'none', name='accountingtype')
    accountingtype.create(op.get_bind(), checkfirst=True)

    op.add_column('tenants', sa.Column(
        'accounting_type',
        accountingtype,
        nullable=False,
        server_default='none',
    ))
    op.add_column('tenants', sa.Column(
        'accounting_credentials',
        sa.Text(),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('tenants', 'accounting_credentials')
    op.drop_column('tenants', 'accounting_type')
    sa.Enum(name='accountingtype').drop(op.get_bind(), checkfirst=True)
