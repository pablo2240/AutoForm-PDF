import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["APP_ENVIRONMENT"] = "test"

from backend.main import app
from backend.db.models import Base, CommercialProfile
from backend.db.session import engine, SessionLocal
from backend.db.auth import create_session_token, hash_password

Base.metadata.create_all(bind=engine)
client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup_test_profiles():
    yield
    db = SessionLocal()
    try:
        db.query(CommercialProfile).filter(
            CommercialProfile.email.like("%test_access_%")
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def create_test_profile(email: str, role: str = "commercial", profile_name: str = "Test User") -> CommercialProfile:
    db = SessionLocal()
    try:
        existing = db.query(CommercialProfile).filter(CommercialProfile.email == email.lower()).first()
        if existing:
            return existing
        p = CommercialProfile(
            id=str(uuid.uuid4()),
            profile_name=profile_name,
            nombre="Test",
            apellido="User",
            cargo="Comercial" if role == "commercial" else "Administrador",
            email=email.lower(),
            celular="3001234567",
            role=role,
            password_hash=hash_password("Password123!"),
            is_active=True
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p
    finally:
        db.close()


def test_public_commercial_profiles_returns_all_active():
    """Valida que GET /api/commercial-profiles retorna todos los perfiles comerciales activos."""
    p1 = create_test_profile("test_access_user1@iaclatam.com", "commercial", "Perfil Comercial 1")
    p2 = create_test_profile("test_access_user2@iaclatam.com", "commercial", "Perfil Comercial 2")

    res = client.get("/api/commercial-profiles")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    emails = [item["email"].lower() for item in data]
    assert p1.email.lower() in emails
    assert p2.email.lower() in emails


def test_commercial_user_can_check_auth():
    """Valida que un usuario comercial autenticado recibe authenticated: True en /api/auth/check."""
    user = create_test_profile("test_access_comm_check@iaclatam.com", "commercial", "Asesor Comercial")
    token = create_session_token(user.email, user.role)

    res = client.get("/api/auth/check", cookies={"admin_session": token})
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is True
    assert data["email"] == user.email
    assert data["role"] == "commercial"


def test_commercial_user_can_list_profiles_in_modal():
    """Valida que un usuario comercial autenticado puede listar los perfiles en /api/admin/commercial-profiles."""
    user = create_test_profile("test_access_comm_list@iaclatam.com", "commercial", "Asesor Comercial")
    token = create_session_token(user.email, user.role)

    res = client.get("/api/admin/commercial-profiles", cookies={"admin_session": token})
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    emails = [item["email"].lower() for item in data]
    assert user.email.lower() in emails


def test_commercial_user_can_create_profile():
    """Valida que un usuario comercial autenticado puede agregar un perfil comercial."""
    user = create_test_profile("test_access_comm_creator@iaclatam.com", "commercial", "Asesor Creador")
    token = create_session_token(user.email, user.role)

    new_email = f"test_access_created_{uuid.uuid4().hex[:6]}@iaclatam.com"
    payload = {
        "profile_name": "Nuevo Colega Comercial",
        "nombre": "Nuevo",
        "apellido": "Colega",
        "cargo": "Consultor Comercial",
        "email": new_email,
        "celular": "3109876543",
        "role": "commercial"
    }

    res = client.post("/api/admin/commercial-profiles", json=payload, cookies={"admin_session": token})
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == new_email.lower()
    assert data["role"] == "commercial"
    assert data["profile_name"] == "Nuevo Colega Comercial"


def test_commercial_user_cannot_force_admin_role_on_created_profile():
    """Valida que un comercial no puede elevar privilegios creando un admin."""
    user = create_test_profile("test_access_comm_unpriv@iaclatam.com", "commercial", "Asesor Regular")
    token = create_session_token(user.email, user.role)

    new_email = f"test_access_unpriv_{uuid.uuid4().hex[:6]}@iaclatam.com"
    payload = {
        "profile_name": "Intento de Admin",
        "nombre": "Intento",
        "apellido": "Admin",
        "cargo": "Director",
        "email": new_email,
        "celular": "3109876543",
        "role": "admin"
    }

    res = client.post("/api/admin/commercial-profiles", json=payload, cookies={"admin_session": token})
    assert res.status_code == 200
    data = res.json()
    # Debe forzarse a "commercial"
    assert data["role"] == "commercial"


def test_commercial_user_can_update_own_profile_but_not_others():
    """Valida que un comercial solo puede actualizar su propio perfil."""
    user1 = create_test_profile("test_access_own1@iaclatam.com", "commercial", "Mi Perfil Propio")
    user2 = create_test_profile("test_access_other2@iaclatam.com", "commercial", "Perfil de Otro")

    token1 = create_session_token(user1.email, user1.role)

    # Puede actualizar el suyo
    update_own = client.put(
        f"/api/admin/commercial-profiles/{user1.id}",
        json={"cargo": "Asesor Senior Actualizado"},
        cookies={"admin_session": token1}
    )
    assert update_own.status_code == 200
    assert update_own.json()["cargo"] == "Asesor Senior Actualizado"

    # NO puede actualizar el de otro
    update_other = client.put(
        f"/api/admin/commercial-profiles/{user2.id}",
        json={"cargo": "Hacked"},
        cookies={"admin_session": token1}
    )
    assert update_other.status_code == 403


def test_commercial_user_cannot_delete_profiles():
    """Valida que un comercial no puede desactivar/eliminar perfiles (solo administradores)."""
    user = create_test_profile("test_access_deleter@iaclatam.com", "commercial", "Asesor")
    target = create_test_profile("test_access_target@iaclatam.com", "commercial", "Objetivo")

    token = create_session_token(user.email, user.role)

    res = client.delete(f"/api/admin/commercial-profiles/{target.id}", cookies={"admin_session": token})
    assert res.status_code == 403
