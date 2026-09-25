import os
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock
import jwt
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set test environment
os.environ["APP_ENVIRONMENT"] = "test"
os.environ["SUPABASE_URL"] = "https://tnhedxwbpqihlqbtzudt.supabase.co"
os.environ["SUPABASE_ANON_KEY"] = "test_anon_key_for_signing_tokens_1234567890"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "test_service_role_key_for_signing_tokens_1234567890"

from backend.main import app
from backend.auth_supabase import (
    decode_supabase_jwt,
    EXPECTED_ISSUER,
    SUPABASE_SERVICE_ROLE_KEY
)

client = TestClient(app)

TEST_USER_ID = str(uuid.uuid4())
TEST_COMPANY_ID = str(uuid.uuid4())

def create_mock_jwt(
    sub: str = TEST_USER_ID,
    role: str = "authenticated",
    email: str = "admin@iaclatam.com",
    company_id: str = TEST_COMPANY_ID,
    user_role: str = "admin",
    issuer: str = EXPECTED_ISSUER,
    expires_in: int = 3600,
    secret: str = SUPABASE_SERVICE_ROLE_KEY
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "role": role,
        "email": email,
        "iss": issuer,
        "iat": now,
        "exp": now + expires_in,
        "app_metadata": {
            "company_id": company_id,
            "role": user_role
        },
        "user_metadata": {
            "nombre": "Admin",
            "apellido": "Tester"
        }
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_decode_jwt_expired():
    """Token expirado debe retornar HTTP 401."""
    expired_token = create_mock_jwt(expires_in=-60)
    with pytest.raises(Exception) as exc_info:
        decode_supabase_jwt(expired_token)
    assert exc_info.value.status_code == 401
    assert "expirado" in exc_info.value.detail.lower()


def test_decode_jwt_invalid_issuer():
    """Token de otro proyecto Supabase (issuer distinto) debe retornar HTTP 401."""
    foreign_token = create_mock_jwt(issuer="https://other-project.supabase.co/auth/v1")
    with pytest.raises(Exception) as exc_info:
        decode_supabase_jwt(foreign_token)
    assert exc_info.value.status_code == 401
    assert "emisor inválido" in exc_info.value.detail.lower() or "otro proyecto" in exc_info.value.detail.lower()


def test_decode_jwt_invalid_sub():
    """Token con sub no UUID debe retornar HTTP 401."""
    bad_sub_token = create_mock_jwt(sub="not-a-valid-uuid")
    with pytest.raises(Exception) as exc_info:
        decode_supabase_jwt(bad_sub_token)
    assert exc_info.value.status_code == 401
    assert "uuid válido" in exc_info.value.detail.lower()


def test_require_admin_active_success():
    """Admin activo en base de datos: permitido (HTTP 200)."""
    valid_token = create_mock_jwt(user_role="admin")

    mock_profile = {
        "id": TEST_USER_ID,
        "company_id": TEST_COMPANY_ID,
        "role": "admin",
        "is_active": True,
        "nombre": "Admin",
        "apellido": "Tester",
        "cargo": "Administrador General",
        "email": "admin@iaclatam.com"
    }

    mock_admin_client = MagicMock()
    mock_query = MagicMock()
    mock_admin_client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.single.return_value = mock_query
    mock_query.execute.return_value.data = mock_profile

    with patch("backend.auth_supabase.get_supabase_admin_client", return_value=mock_admin_client), \
         patch("backend.auth_supabase.get_supabase_user_client", return_value=MagicMock()):
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {valid_token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert data["is_active"] is True


def test_require_admin_demoted_to_commercial_blocked():
    """
    Admin degradado a comercial en BD (aunque su JWT diga role='admin'):
    Debe ser rechazado inmediatamente con HTTP 403 en require_admin.
    """
    # JWT claims still say role='admin'
    admin_token_from_past = create_mock_jwt(user_role="admin")

    # Authoritative database profile says role='commercial'
    demoted_profile = {
        "id": TEST_USER_ID,
        "company_id": TEST_COMPANY_ID,
        "role": "commercial",  # DEGRADED!
        "is_active": True,
        "nombre": "Ex-Admin",
        "apellido": "Tester",
        "cargo": "Asesor Comercial",
        "email": "admin@iaclatam.com"
    }

    mock_admin_client = MagicMock()
    mock_query = MagicMock()
    mock_admin_client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.single.return_value = mock_query
    mock_query.execute.return_value.data = demoted_profile

    with patch("backend.auth_supabase.get_supabase_admin_client", return_value=mock_admin_client), \
         patch("backend.auth_supabase.get_supabase_user_client", return_value=MagicMock()):
        # Try accessing admin endpoint (invite-user requires require_admin)
        response = client.post(
            "/api/admin/invite-user",
            headers={"Authorization": f"Bearer {admin_token_from_past}"},
            json={
                "email": "nuevo@iaclatam.com",
                "nombre": "Nuevo",
                "apellido": "Usuario",
                "cargo": "Asesor",
                "celular": "3001234567",
                "role": "commercial"
            }
        )
        assert response.status_code == 403
        assert "insuficientes" in response.json()["detail"].lower() or "revocado" in response.json()["detail"].lower()


def test_require_admin_deactivated_blocked():
    """
    Admin suspendido o desactivado (is_active=False en BD):
    Debe ser rechazado inmediatamente con HTTP 403, invalidando el JWT no expirado.
    """
    admin_token = create_mock_jwt(user_role="admin")

    deactivated_profile = {
        "id": TEST_USER_ID,
        "company_id": TEST_COMPANY_ID,
        "role": "admin",
        "is_active": False,  # DEACTIVATED / SUSPENDED!
        "nombre": "Blocked Admin",
        "apellido": "Tester",
        "email": "admin@iaclatam.com"
    }

    mock_admin_client = MagicMock()
    mock_query = MagicMock()
    mock_admin_client.table.return_value = mock_query
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.single.return_value = mock_query
    mock_query.execute.return_value.data = deactivated_profile

    with patch("backend.auth_supabase.get_supabase_admin_client", return_value=mock_admin_client), \
         patch("backend.auth_supabase.get_supabase_user_client", return_value=MagicMock()):
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 403
        assert "inactiva" in response.json()["detail"].lower() or "suspendida" in response.json()["detail"].lower()


# =============================================================================
# ENVIRONMENT CONFIGURATION HARDENING TESTS (CORS_ORIGINS & SESSION_SECRET)
# =============================================================================
from backend.main import resolve_cors_origins
from backend.db.auth import resolve_session_secret, INSECURE_DEFAULT_SECRETS

def test_cors_origins_production_fails_when_unset():
    """Producción falla si CORS_ORIGINS no está definido o está vacío."""
    with pytest.raises(RuntimeError, match="CORS_ORIGINS environment variable is required"):
        resolve_cors_origins(app_env="production", raw_origins="")

    with pytest.raises(RuntimeError, match="CORS_ORIGINS environment variable is required"):
        resolve_cors_origins(app_env="production", raw_origins=None)


def test_cors_origins_production_fails_with_wildcard():
    """Producción rechaza estrictamente el comodín '*' en CORS_ORIGINS."""
    with pytest.raises(RuntimeError, match="wildcard '\\*' is strictly forbidden"):
        resolve_cors_origins(app_env="production", raw_origins="*")

    with pytest.raises(RuntimeError, match="wildcard '\\*' is strictly forbidden"):
        resolve_cors_origins(app_env="production", raw_origins="https://autoform.iaclatam.com, *")


def test_cors_origins_production_fails_with_localhost_only():
    """Producción rechaza orígenes localhost o 127.0.0.1 y falla si no queda ninguno válido."""
    with pytest.raises(RuntimeError, match="valid non-localhost origin"):
        resolve_cors_origins(app_env="production", raw_origins="http://localhost:5173, http://127.0.0.1:3000")


def test_cors_origins_production_succeeds_with_valid_origins():
    """Producción acepta dominios válidos y filtra cualquier localhost remanente."""
    origins = resolve_cors_origins(
        app_env="production",
        raw_origins="https://autoform.iaclatam.com, http://localhost:5173"
    )
    assert origins == ["https://autoform.iaclatam.com"]


def test_cors_origins_staging_fails_when_unset():
    """Staging exige CORS_ORIGINS explícito y no permite fallback permisivo."""
    with pytest.raises(RuntimeError, match="CORS_ORIGINS environment variable is required"):
        resolve_cors_origins(app_env="staging", raw_origins="")


def test_cors_origins_local_preserves_default_configuration():
    """Desarrollo local conserva los orígenes permitidos por defecto sin requerir variable."""
    local_origins = resolve_cors_origins(app_env="local", raw_origins="")
    assert "http://localhost:5173" in local_origins
    assert "http://127.0.0.1:5173" in local_origins

    custom_local = resolve_cors_origins(app_env="local", raw_origins="http://custom-dev:8000")
    assert custom_local == ["http://custom-dev:8000"]


def test_session_secret_production_fails_when_unset():
    """Producción falla si SESSION_SECRET no está definido."""
    with pytest.raises(RuntimeError, match="SESSION_SECRET environment variable is required"):
        resolve_session_secret(app_env="production", raw_secret="")

    with pytest.raises(RuntimeError, match="SESSION_SECRET environment variable is required"):
        resolve_session_secret(app_env="production", raw_secret=None)


def test_session_secret_production_fails_with_insecure_defaults():
    """Producción falla si SESSION_SECRET usa valores conocidos o inseguros por defecto."""
    for insecure in INSECURE_DEFAULT_SECRETS:
        with pytest.raises(RuntimeError, match="known or insecure default value"):
            resolve_session_secret(app_env="production", raw_secret=insecure)


def test_session_secret_production_fails_when_shorter_than_32_chars():
    """Producción y staging rechazan cualquier SESSION_SECRET con menos de 32 caracteres."""
    short_secret = "short_key_12345"  # 15 chars (< 32)
    with pytest.raises(RuntimeError, match="at least 32 characters long"):
        resolve_session_secret(app_env="production", raw_secret=short_secret)

    with pytest.raises(RuntimeError, match="at least 32 characters long"):
        resolve_session_secret(app_env="staging", raw_secret=short_secret)


def test_session_secret_does_not_leak_value_in_error():
    """El mensaje de error no imprime ni expone el valor del secreto ingresado."""
    candidate = "candidate_key_under_32"
    with pytest.raises(RuntimeError) as exc_info:
        resolve_session_secret(app_env="production", raw_secret="iac_secret_signing_key_2026")
    assert "iac_secret_signing_key_2026" not in str(exc_info.value)

    with pytest.raises(RuntimeError) as exc_info:
        resolve_session_secret(app_env="production", raw_secret=candidate)
    assert candidate not in str(exc_info.value)


def test_session_secret_production_succeeds_with_secure_secret():
    """Producción acepta un secreto seguro de al menos 32 caracteres."""
    sec = "b9f71c48e02d8471e95c10ad8234567890abcdef1234567890abcdef"  # 58 chars
    res = resolve_session_secret(app_env="production", raw_secret=sec)
    assert res == sec


def test_session_secret_staging_fails_when_unset():
    """Staging exige SESSION_SECRET explícito y no permite fallback."""
    with pytest.raises(RuntimeError, match="SESSION_SECRET environment variable is required"):
        resolve_session_secret(app_env="staging", raw_secret="")


def test_session_secret_local_preserves_default_configuration():
    """Desarrollo local conserva el valor controlado por defecto si no está definido."""
    local_sec = resolve_session_secret(app_env="local", raw_secret="")
    assert local_sec == "iac_secret_signing_key_2026"

    custom_sec = resolve_session_secret(app_env="local", raw_secret="custom_local_key")
    assert custom_sec == "custom_local_key"
