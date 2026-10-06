import os
import sys
import uuid
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["APP_ENVIRONMENT"] = "test"

from backend.main import app, DATA_DIR
from backend.db.models import Base, CommercialProfile
from backend.db.session import engine, SessionLocal
from backend.db.auth import create_session_token, hash_password

Base.metadata.create_all(bind=engine)
client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup_test_data():
    yield
    db = SessionLocal()
    try:
        db.query(CommercialProfile).filter(
            CommercialProfile.email.like("%test_sync_%")
        ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_get_employer_profiles_returns_profiles_with_cargo():
    """Valida que GET /api/employer-profiles retorna perfiles con el campo cargo."""
    res = client.get("/api/employer-profiles")
    assert res.status_code == 200
    profiles = res.json()
    assert isinstance(profiles, list)
    assert len(profiles) > 0

    for p in profiles:
        assert "cargo" in p, f"Perfil {p.get('profileName')} no tiene campo 'cargo'"
        assert "profileName" in p
        assert "email" in p
        assert "celular" in p


def test_post_employer_profiles_persists_cargo_and_data():
    """Valida que POST /api/employer-profiles persiste el nuevo perfil con su cargo."""
    unique_id = uuid.uuid4().hex[:6]
    test_email = f"test_sync_emp_{unique_id}@iaclatam.com"
    test_cargo = "Líder de Soporte Técnico"

    new_profile = {
        "id": f"prof-{unique_id}",
        "profileName": f"Carlos Test {unique_id}",
        "nombre": "Carlos",
        "apellido": f"Test {unique_id}",
        "cargo": test_cargo,
        "email": test_email,
        "celular": "3119876543",
        "customFields": []
    }

    # Obtener actuales y anexar
    res_get = client.get("/api/employer-profiles")
    current_list = res_get.json()
    current_list.append(new_profile)

    res_post = client.post("/api/employer-profiles", json=current_list)
    assert res_post.status_code == 200
    assert res_post.json()["status"] == "success"

    # Verificar que al volver a consultar GET /api/employer-profiles el perfil y su cargo existen
    res_verify = client.get("/api/employer-profiles")
    assert res_verify.status_code == 200
    updated_profiles = res_verify.json()
    found = next((p for p in updated_profiles if p.get("email") == test_email.lower()), None)
    assert found is not None, f"No se encontró el perfil con email {test_email}"
    assert found.get("cargo") == test_cargo

    # Verificar persistencia en SQLite
    db = SessionLocal()
    try:
        cp = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(test_email)).first()
        assert cp is not None
        assert cp.cargo == test_cargo
        assert cp.nombre == "Carlos"
    finally:
        db.close()


def test_create_commercial_profile_with_cargo_updates_employer_list():
    """Valida que crear un perfil comercial vía POST /api/admin/commercial-profiles incluye cargo y se refleja en employer profiles."""
    db = SessionLocal()
    admin_user = db.query(CommercialProfile).filter(CommercialProfile.role == "admin", CommercialProfile.is_active == True).first()
    if not admin_user:
        admin_user = CommercialProfile(
            id=str(uuid.uuid4()),
            profile_name="Admin Test",
            nombre="Admin",
            apellido="Test",
            cargo="Administrador General",
            email="test_sync_admin@iaclatam.com",
            celular="3001234567",
            role="admin",
            password_hash=hash_password("Pass123!"),
            is_active=True
        )
        db.add(admin_user)
        db.commit()
    token = create_session_token(admin_user.email, admin_user.role)
    db.close()

    unique_id = uuid.uuid4().hex[:6]
    new_email = f"test_sync_comm_{unique_id}@iaclatam.com"
    new_cargo = "Gerente de Cuentas Estratégicas"

    payload = {
        "profile_name": f"Melisa Comercial {unique_id}",
        "nombre": "Melisa",
        "apellido": f"Comercial {unique_id}",
        "cargo": new_cargo,
        "email": new_email,
        "celular": "3201234567",
        "role": "commercial"
    }

    res_post = client.post("/api/admin/commercial-profiles", json=payload, cookies={"admin_session": token})
    assert res_post.status_code == 200
    data = res_post.json()
    assert data["email"] == new_email.lower()
    assert data["cargo"] == new_cargo

    # Verificar que GET /api/employer-profiles ahora incluye a Melisa con su cargo
    res_emp = client.get("/api/employer-profiles")
    assert res_emp.status_code == 200
    emp_list = res_emp.json()
    found = next((p for p in emp_list if p.get("email") == new_email.lower()), None)
    assert found is not None
    assert found.get("cargo") == new_cargo


def test_company_data_get_and_post_persistence():
    """Valida que GET y POST /api/company-data funcionan y persisten correctamente."""
    res_get = client.get("/api/company-data")
    assert res_get.status_code == 200
    comp_data = res_get.json()
    assert "razon_social" in comp_data
    assert "nit" in comp_data
    assert "representante_legal" in comp_data

    # Guardar actualización
    comp_data["direccion_principal"] = "Carrera 63 B # 32 E -25 OFC 206"
    res_post = client.post("/api/company-data", json=comp_data)
    assert res_post.status_code == 200
    assert res_post.json()["status"] == "success"
