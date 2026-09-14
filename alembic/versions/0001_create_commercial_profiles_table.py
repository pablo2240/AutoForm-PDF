"""create commercial_profiles table with seed data

Revision ID: 0001_create_commercial_profiles
Revises: 
Create Date: 2026-09-14 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision: str = '0001_create_commercial_profiles'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create table
    commercial_profiles = op.create_table(
        'commercial_profiles',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('profile_name', sa.String(length=100), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('apellido', sa.String(length=100), nullable=False),
        sa.Column('cargo', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False, unique=True),
        sa.Column('celular', sa.String(length=50), nullable=False),
        sa.Column('tipo_documento', sa.String(length=20), nullable=True, server_default='C.C'),
        sa.Column('documento_identidad', sa.String(length=50), nullable=True),
        sa.Column('role', sa.String(length=30), nullable=False, server_default='commercial'),
        sa.Column('password_hash', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('last_modified_by_ip', sa.String(length=45), nullable=True)
    )

    # 2. Idempotent seed for Guillermo Cañón (Admin) and Kelly Delgado (Commercial)
    op.bulk_insert(
        commercial_profiles,
        [
            {
                'id': 'prof-guillermo-canon',
                'profile_name': 'Guillermo Cañón',
                'nombre': 'Guillermo Humberto',
                'apellido': 'Cañón Sarria',
                'cargo': 'Representante Legal / Gerente General',
                'email': 'guillermo.canon@iaclatam.com',
                'celular': '3104120217',
                'tipo_documento': 'C.C',
                'documento_identidad': '98555384',
                'role': 'admin',
                'password_hash': 'b0d8c21f4dd59f2b025842534e9fae35:d42a9af3d38a8d09939d7fafa9781f9e60c67f0df8b3163cd4da9d75a2fecee0',
                'is_active': True,
            },
            {
                'id': 'prof-kelly-delgado',
                'profile_name': 'Kelly Delgado',
                'nombre': 'Kelly Yohana',
                'apellido': 'Delgado Macea',
                'cargo': 'Asesor Comercial',
                'email': 'Kelly.Delgado@iaclatam.com',
                'celular': '301 4750760',
                'tipo_documento': 'C.C',
                'documento_identidad': None,
                'role': 'commercial',
                'password_hash': 'fe955f793e3e73cc5f77c27c5b76bf28:86b1f54c8a6f1332255b75d23c555c362650bea9958d886773a4ca34c45ffe99',
                'is_active': True,
            }
        ]
    )


def downgrade() -> None:
    op.drop_table('commercial_profiles')
