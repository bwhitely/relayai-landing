"""add calendar_type and calendar_credentials

Revision ID: a1b2c3d4e5f6
Revises: f27af717cb92
Create Date: 2026-02-13 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f27af717cb92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    calendartype = sa.Enum('google_calendar', 'calendly', 'none', name='calendartype')
    calendartype.create(op.get_bind(), checkfirst=True)

    op.add_column('tenants', sa.Column(
        'calendar_type',
        calendartype,
        nullable=False,
        server_default='none',
    ))
    op.add_column('tenants', sa.Column(
        'calendar_credentials',
        sa.Text(),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('tenants', 'calendar_credentials')
    op.drop_column('tenants', 'calendar_type')
    sa.Enum(name='calendartype').drop(op.get_bind(), checkfirst=True)
