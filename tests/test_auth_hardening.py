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
