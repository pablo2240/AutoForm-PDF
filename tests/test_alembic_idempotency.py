import os
import sqlite3
from pathlib import Path
from alembic.config import Config
from alembic import command
import sqlalchemy as sa
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def test_alembic_idempotent_upgrade_with_preexisting_user_documents(tmp_path):
    test_db_path = tmp_path / "test_migration_idempotent.db"
    test_db_url = f"sqlite:///{test_db_path.as_posix()}"

    alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    alembic_cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))

    import backend.db.session
    backend.db.session.database_url = test_db_url

    # 1. Migrar hasta la revisión 0003_case_insensitive_email
    command.upgrade(alembic_cfg, "0003_case_insensitive_email")

    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT version_num FROM alembic_version")
    row = cursor.fetchone()
    assert row[0] == "0003_case_insensitive_email"

    # 2. Simular que la tabla user_documents ya existe en Neon antes de correr 0005
    cursor.execute("""
    CREATE TABLE user_documents (
        id VARCHAR(36) PRIMARY KEY,
        company_id VARCHAR(36) NOT NULL,
        user_id VARCHAR(36) NOT NULL,
        template_code VARCHAR(100),
        filename VARCHAR(255) NOT NULL,
        storage_path VARCHAR(500) NOT NULL,
        size_kb FLOAT,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    INSERT INTO user_documents (id, company_id, user_id, filename, storage_path)
    VALUES ('doc-existing-neon-1', 'comp-1', 'user-1', 'formulario_cliente.pdf', 'storage/path/1')
    """)
    conn.commit()
    conn.close()

    # 3. Ejecutar alembic upgrade head (debe correr 0004 y 0005 sin fallar por DuplicateTable)
    command.upgrade(alembic_cfg, "head")

    engine = sa.create_engine(test_db_url)
    inspector = sa.inspect(engine)

    # 4. Verificar creación de password_reset_tokens por 0004
    assert inspector.has_table("password_reset_tokens")

    # 5. Verificar preservación de user_documents y sus datos
    assert inspector.has_table("user_documents")
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename FROM user_documents WHERE id = 'doc-existing-neon-1'")
    doc_row = cursor.fetchone()
    assert doc_row is not None and doc_row[1] == "formulario_cliente.pdf"

    # 6. Verificar índices de user_documents
    indexes = {idx["name"] for idx in inspector.get_indexes("user_documents")}
    assert "idx_user_documents_user_active" in indexes
    assert "idx_user_documents_company" in indexes

    # 7. Verificar revisión final en alembic_version
    cursor.execute("SELECT version_num FROM alembic_version")
    final_version = cursor.fetchone()[0]
    conn.close()
    engine.dispose()

    assert final_version == "0005_create_user_documents"


def test_alembic_non_destructive_downgrade_preserves_user_documents(tmp_path):
    """
    Verifica que:
    1. user_documents existe con datos antes de aplicar 0005.
    2. Se ejecuta la migración a head (0005).
    3. Se ejecuta el downgrade a 0004_password_reset_tokens.
    4. La tabla user_documents y sus datos siguen existiendo intactos.
    """
    test_db_path = tmp_path / "test_downgrade_nondestructive.db"
    test_db_url = f"sqlite:///{test_db_path.as_posix()}"

    alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    alembic_cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))

    import backend.db.session
    backend.db.session.database_url = test_db_url

    # 1. Migrar a 0004_password_reset_tokens
    command.upgrade(alembic_cfg, "0004_password_reset_tokens")

    # 2. Insertar tabla user_documents con datos existentes antes de aplicar 0005
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE user_documents (
        id VARCHAR(36) PRIMARY KEY,
        company_id VARCHAR(36) NOT NULL,
        user_id VARCHAR(36) NOT NULL,
        template_code VARCHAR(100),
        filename VARCHAR(255) NOT NULL,
        storage_path VARCHAR(500) NOT NULL,
        size_kb FLOAT,
        is_active BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    INSERT INTO user_documents (id, company_id, user_id, filename, storage_path)
    VALUES ('doc-preserve-1', 'comp-99', 'user-99', 'contrato_critico.pdf', 'storage/preserve/1')
    """)
    conn.commit()
    conn.close()

    # 3. Aplicar migración 0005 (head)
    command.upgrade(alembic_cfg, "head")

    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT version_num FROM alembic_version")
    assert cursor.fetchone()[0] == "0005_create_user_documents"
    conn.close()

    # 4. Ejecutar downgrade explícito a 0004_password_reset_tokens
    command.downgrade(alembic_cfg, "0004_password_reset_tokens")

    # 5. Comprobar que alembic_version retrocedió a 0004_password_reset_tokens
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT version_num FROM alembic_version")
    downgraded_version = cursor.fetchone()[0]
    assert downgraded_version == "0004_password_reset_tokens"

    # 6. Comprobar que la tabla user_documents y sus datos siguen existiendo
    cursor.execute("SELECT id, filename FROM user_documents WHERE id = 'doc-preserve-1'")
    row = cursor.fetchone()
    assert row is not None
    assert row[1] == "contrato_critico.pdf"
    conn.close()

    engine = sa.create_engine(test_db_url)
    inspector = sa.inspect(engine)
    assert inspector.has_table("user_documents")
    engine.dispose()
