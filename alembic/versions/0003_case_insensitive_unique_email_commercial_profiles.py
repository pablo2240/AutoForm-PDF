"""case insensitive unique index on commercial_profiles lower(email)

Revision ID: 0003_case_insensitive_email
Revises: 0002_add_ciudad
Create Date: 2026-09-25 08:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003_case_insensitive_email'
down_revision: Union[str, None] = '0002_add_ciudad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_commercial_profiles_email_lower ON commercial_profiles (LOWER(email))")
    )


def downgrade() -> None:
    op.execute(
        sa.text("DROP INDEX IF EXISTS uq_commercial_profiles_email_lower")
    )
