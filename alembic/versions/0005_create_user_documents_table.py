"""create user_documents table with single-active index

Revision ID: 0005_create_user_documents
Revises: 0004_password_reset_tokens
Create Date: 2026-10-01 14:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005_create_user_documents'
down_revision: Union[str, None] = '0004_password_reset_tokens'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_documents',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('company_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('template_code', sa.String(length=100), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=False),
        sa.Column('size_kb', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    op.create_index(
        'idx_user_documents_user_active',
        'user_documents',
        ['user_id', 'is_active'],
        unique=False
    )
    op.create_index(
        'idx_user_documents_company',
        'user_documents',
        ['company_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('idx_user_documents_company', table_name='user_documents')
    op.drop_index('idx_user_documents_user_active', table_name='user_documents')
    op.drop_table('user_documents')
