"""add ciudad to commercial_profiles

Revision ID: 0002_add_ciudad
Revises: 0001_create_commercial_profiles
Create Date: 2026-09-25 08:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_add_ciudad'
down_revision: Union[str, None] = '0001_create_commercial_profiles'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'commercial_profiles',
        sa.Column('ciudad', sa.String(length=100), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('commercial_profiles', 'ciudad')
