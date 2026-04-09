"""Add tag team finisher name column

Revision ID: a1b2c3d4e5f6
Revises: 1706a93ccd41
Create Date: 2026-04-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '1706a93ccd41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tag_teams', sa.Column('team_finisher_name', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('tag_teams', 'team_finisher_name')
