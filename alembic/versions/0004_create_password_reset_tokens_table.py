"""create password_reset_tokens table and add needs_password_hash_sync

Revision ID: 0004_create_password_reset_tokens
Revises: 0003_case_insensitive_email
Create Date: 2026-10-01 13:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004_create_password_reset_tokens'
down_revision: Union[str, None] = '0003_case_insensitive_email'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create password_reset_tokens table
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('request_ip', sa.String(length=45), nullable=True)
    )

    op.create_index(
        'ix_password_reset_tokens_token_hash',
        'password_reset_tokens',
        ['token_hash'],
        unique=True
    )
    op.create_index(
        'ix_password_reset_tokens_user_id',
        'password_reset_tokens',
        ['user_id'],
        unique=False
    )

    # 2. Add needs_password_hash_sync column to commercial_profiles
    op.add_column(
        'commercial_profiles',
        sa.Column('needs_password_hash_sync', sa.Boolean(), nullable=True, server_default=sa.false())
    )


def downgrade() -> None:
    op.drop_column('commercial_profiles', 'needs_password_hash_sync')
    op.drop_index('ix_password_reset_tokens_user_id', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_tokens_token_hash', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
