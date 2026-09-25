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

from backend.main import app, registration_rate_limiter, check_email_rate_limiter
from backend.db.models import Base, CommercialProfile
from backend.db.session import engine, SessionLocal
from backend.db.auth import verify_password
from sqlalchemy.exc import IntegrityError

# Ensure schema exists in test database
Base.metadata.create_all(bind=engine)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    """Reset rate limiters and clean state before/after each test."""
    registration_rate_limiter.reset()
    check_email_rate_limiter.reset()
    yield
    registration_rate_limiter.reset()
    check_email_rate_limiter.reset()

def _unique_email(prefix: str = "comercial") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@iaclatam.com"


# ==============================================================================
# 1. Successful Registration & Persistence
# ==============================================================================

def test_commercial_registration_success():
    """Registro exitoso crea el perfil activo con rol comercial, ciudad y emite sesión inmediata."""
    email = _unique_email("registro_valido")
    payload = {
        "nombre": "Carlos",
        "apellido": "Gómez",
        "cargo": "Consultor Senior",
        "email": email,
        "celular": "3109876543",
        "tipo_documento": "CC",
        "documento_identidad": "1018456789",
        "ciudad": "Bogotá D.C.",
        "password": "Password123456!" # >= 12 chars
    }

    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["status"] == "success"
    assert data["authenticated"] is True
    assert data["email"] == email.lower()
    assert data["role"] == "commercial"
    assert data["nombre"] == "Carlos"
    assert data["apellido"] == "Gómez"
    assert data["cargo"] == "Consultor Senior"
    assert data["ciudad"] == "Bogotá D.C."
    assert "token" in data and len(data["token"]) > 20
    assert "password" not in data
    assert "password_hash" not in data

    # Verify session cookie was set
    assert "admin_session" in res.cookies

    # Verify database persistence
    db = SessionLocal()
    try:
        user = db.query(CommercialProfile).filter(CommercialProfile.email == email.lower()).first()
        assert user is not None
        assert user.is_active is True
        assert user.role == "commercial"
        assert user.ciudad == "Bogotá D.C."
        assert user.documento_identidad == "1018456789"
        assert user.celular == "3109876543"
        assert verify_password("Password123456!", user.password_hash)
        assert "Password123456!" not in user.password_hash
    finally:
        db.close()


# ==============================================================================
# 2. Supabase Auth Mocks: Success, Failure, and Compensation
# ==============================================================================

def test_registration_supabase_auth_success():
    """Confirma que POST /api/auth/register crea el usuario en Supabase Auth con email_confirm=True y app_metadata impuesta."""
    email = _unique_email("sb_success")
    auth_user_uuid = str(uuid.uuid4())
    mock_company_uuid = str(uuid.uuid4())

    mock_admin_client = MagicMock()
    mock_auth_user = MagicMock()
    mock_auth_user.id = auth_user_uuid
    mock_admin_client.auth.admin.create_user.return_value = MagicMock(user=mock_auth_user)

    # Mock companies query
    mock_comp_res = MagicMock()
    mock_comp_res.data = [{"id": mock_company_uuid}]
    mock_admin_client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = mock_comp_res

    payload = {
        "nombre": "Esteban",
        "apellido": "Morales",
        "cargo": "Director Comercial",
        "email": email,
        "celular": "3115556677",
        "tipo_documento": "CC",
        "documento_identidad": "79888999",
        "ciudad": "Medellín",
        "password": "SecurePassword2026!" # 19 chars >= 12
    }

    with patch("backend.main.get_supabase_admin_client", return_value=mock_admin_client):
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 200, res.text

    # Verify create_user called with required administrative properties
    mock_admin_client.auth.admin.create_user.assert_called_once()
    called_payload = mock_admin_client.auth.admin.create_user.call_args[0][0]

    assert called_payload["email"] == email.lower()
    assert called_payload["email_confirm"] is True
    assert called_payload["app_metadata"]["role"] == "commercial"
    assert called_payload["app_metadata"]["is_active"] is True
    assert called_payload["app_metadata"]["company_id"] == mock_company_uuid
    assert called_payload["user_metadata"]["nombre"] == "Esteban"
    assert called_payload["user_metadata"]["ciudad"] == "Medellín"

    # Verify local profile has the same UUID issued by Supabase Auth
    db = SessionLocal()
    try:
        user = db.query(CommercialProfile).filter(CommercialProfile.id == auth_user_uuid).first()
        assert user is not None
        assert user.email == email.lower()
        assert user.role == "commercial"
        assert user.is_active is True
    finally:
        db.close()


def test_registration_auth_failure_no_profile_persisted():
    """Si falla la creación en Supabase Auth, no debe persistirse ningún perfil en base de datos."""
    email = _unique_email("sb_fail")

    mock_admin_client = MagicMock()
    mock_admin_client.auth.admin.create_user.side_effect = Exception("Supabase Auth API connection failure")

    payload = {
        "nombre": "Carolina",
        "apellido": "Herrera",
        "cargo": "Asesora Senior",
        "email": email,
        "celular": "3124445566",
        "tipo_documento": "CC",
        "documento_identidad": "52111222",
        "ciudad": "Cartagena",
        "password": "SecurePassword2026!"
    }

    with patch("backend.main.get_supabase_admin_client", return_value=mock_admin_client):
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 400
        assert "Error al registrar usuario en Supabase Auth" in res.json()["detail"]

    # Confirm NO profile was persisted in the database
    db = SessionLocal()
    try:
        user = db.query(CommercialProfile).filter(CommercialProfile.email == email.lower()).first()
        assert user is None
    finally:
        db.close()


def test_registration_profile_failure_triggers_auth_compensation():
    """Si falla la persistencia del perfil tras crear el usuario en Auth, se ejecuta compensación (delete_user) para no dejar cuenta huérfana."""
    email = _unique_email("sb_compensate")
    orphan_uuid = str(uuid.uuid4())

    mock_admin_client = MagicMock()
    mock_auth_user = MagicMock()
    mock_auth_user.id = orphan_uuid
    mock_admin_client.auth.admin.create_user.return_value = MagicMock(user=mock_auth_user)
    mock_admin_client.auth.admin.delete_user = MagicMock()

    payload = {
        "nombre": "Santiago",
        "apellido": "Vargas",
        "cargo": "Consultor Comercial",
        "email": email,
        "celular": "3137778899",
        "tipo_documento": "CC",
        "documento_identidad": "80222333",
        "ciudad": "Manizales",
        "password": "SecurePassword2026!"
    }

    # Simulate database failure during profile commit
    with patch("backend.main.get_supabase_admin_client", return_value=mock_admin_client):
        with patch.object(CommercialProfile, "__init__", side_effect=Exception("Database model initialization error")):
            res = client.post("/api/auth/register", json=payload)
            assert res.status_code == 500
            assert "Error al persistir el perfil comercial" in res.json()["detail"]

    # Compensation MUST have been executed
    mock_admin_client.auth.admin.delete_user.assert_called_once_with(orphan_uuid)

    # Confirm DB has no profile
    db = SessionLocal()
    try:
        user = db.query(CommercialProfile).filter(CommercialProfile.email == email.lower()).first()
        assert user is None
    finally:
        db.close()


# ==============================================================================
# 3. Password Hardening (Minimum 8 Characters)
# ==============================================================================

def test_registration_rejects_password_shorter_than_8():
    """Rechaza contraseñas con menos de 8 caracteres y nunca filtra la contraseña en el error."""
    short_pass = "Pass123" # 7 characters (< 8)
    payload = {
        "nombre": "Gabriel",
        "apellido": "Rincón",
        "cargo": "Asesor de Ventas",
        "email": _unique_email("pwd_short"),
        "celular": "3001234567",
        "documento_identidad": "12345678",
        "ciudad": "Bucaramanga",
        "password": short_pass
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 400
    assert "al menos 8 caracteres" in res.json()["detail"]
    assert short_pass not in res.json()["detail"]


def test_registration_accepts_8_character_password():
    """Acepta contraseñas con exactamente 8 caracteres."""
    pass_8 = "Abc12345" # exactly 8 characters
    payload = {
        "nombre": "Gabriel",
        "apellido": "Rincón",
        "cargo": "Asesor de Ventas",
        "email": _unique_email("pwd_exact8"),
        "celular": "3001234567",
        "documento_identidad": "12345678",
        "ciudad": "Bucaramanga",
        "password": pass_8
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 200
    assert res.json()["authenticated"] is True


# ==============================================================================
# 4. Email Uniqueness & Case-Insensitive Normalization
# ==============================================================================

def test_registration_rejects_duplicate_email_case_insensitive():
    """Garantiza rechazo de correo duplicado insensible a mayúsculas/minúsculas."""
    email_base = _unique_email("case_unique")
    payload = {
        "nombre": "Mariana",
        "apellido": "Torres",
        "cargo": "Especialista Comercial",
        "email": email_base.lower(),
        "celular": "3129876543",
        "documento_identidad": "52890123",
        "ciudad": "Barranquilla",
        "password": "SecurePassword2026!"
    }
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 200

    # Attempt to register with uppercase email
    payload_upper = dict(payload)
    payload_upper["email"] = email_base.upper()
    res2 = client.post("/api/auth/register", json=payload_upper)
    assert res2.status_code == 400
    assert "ya se encuentra registrado" in res2.json()["detail"]

    # Verify the database index enforces this at SQL level
    db = SessionLocal()
    try:
        dup_profile = CommercialProfile(
            profile_name="Mariana Clone",
            nombre="Mariana",
            apellido="Torres",
            cargo="Asesor Comercial",
            email=email_base.upper(),
            celular="3129876543",
            ciudad="Barranquilla",
            role="commercial",
            is_active=True
        )
        db.add(dup_profile)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_registration_rejects_non_corporate_email():
    """Rechaza registros con dominios públicos o no autorizados."""
    invalid_emails = [
        "carlos@gmail.com",
        "usuario@hotmail.com",
        "asesor@empresaexterna.co",
        "test@iac.com", # Must be @iac.com.co or @iaclatam.com
    ]
    for bad_email in invalid_emails:
        payload = {
            "nombre": "Carlos",
            "apellido": "Pérez",
            "cargo": "Asesor Comercial",
            "email": bad_email,
            "celular": "3001234567",
            "documento_identidad": "12345678",
            "ciudad": "Cali",
            "password": "SecurePassword2026!"
        }
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 400
        assert "Dominio de correo no autorizado" in res.json()["detail"]


# ==============================================================================
# 5. Check-Email & Rate Limiting
# ==============================================================================

def test_check_email_availability():
    """Endpoint de verificación de unicidad informa disponibilidad de forma case-insensitive."""
    email = _unique_email("check_avail")

    # Before registration: available
    res = client.get(f"/api/auth/check-email?email={email}")
    assert res.status_code == 200
    assert res.json()["available"] is True
    assert res.json()["exists"] is False

    # Register user
    payload = {
        "nombre": "Laura",
        "apellido": "Mendoza",
        "cargo": "Ejecutiva de Cuenta",
        "email": email,
        "celular": "3151234567",
        "documento_identidad": "1020304050",
        "ciudad": "Medellín",
        "password": "SecurePassword2026!"
    }
    reg_res = client.post("/api/auth/register", json=payload)
    assert reg_res.status_code == 200

    # After registration: unavailable (checked with uppercase)
    res_after = client.get(f"/api/auth/check-email?email={email.upper()}")
    assert res_after.status_code == 200
    assert res_after.json()["available"] is False
    assert res_after.json()["exists"] is True


def test_check_email_rate_limiting():
    """Aplica rate limit a GET /api/auth/check-email bloqueando tras 10 intentos por minuto."""
    check_email_rate_limiter.reset()

    # 10 queries allowed
    for i in range(10):
        res = client.get(f"/api/auth/check-email?email=check_rate_{i}@iaclatam.com")
        assert res.status_code == 200

    # 11th query must be blocked with HTTP 429
    res_blocked = client.get("/api/auth/check-email?email=check_blocked@iaclatam.com")
    assert res_blocked.status_code == 429
    assert "Límite de consultas de verificación de correo excedido" in res_blocked.json()["detail"]

    # Reset restores access
    check_email_rate_limiter.reset()
    res_restored = client.get("/api/auth/check-email?email=check_restored@iaclatam.com")
    assert res_restored.status_code == 200


def test_registration_rate_limiting():
    """Verifica que tras 5 intentos en la ventana de tiempo se retorne HTTP 429 en registro."""
    registration_rate_limiter.reset()

    payload = {
        "nombre": "TestRate",
        "apellido": "Limiting",
        "cargo": "Asesor Comercial",
        "email": _unique_email("rate"),
        "celular": "3001234567",
        "documento_identidad": "12345678",
        "ciudad": "Armenia",
        "password": "SecurePassword2026!"
    }

    # First 5 attempts consume allowance
    for i in range(5):
        payload["email"] = _unique_email(f"rate_{i}")
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 200, f"Attempt {i+1} failed: {res.text}"

    # 6th attempt must be blocked by rate limiter
    payload["email"] = _unique_email("rate_blocked")
    res_blocked = client.post("/api/auth/register", json=payload)
    assert res_blocked.status_code == 429
    assert "Límite de intentos de registro excedido" in res_blocked.json()["detail"]


# ==============================================================================
# 6. Strict Validation Failures (Name, Cargo, Celular, Cédula, Ciudad)
# ==============================================================================

def test_registration_rejects_invalid_names():
    """Rechaza nombres o apellidos con menos de 4 caracteres o con dígitos/símbolos."""
    base_payload = {
        "nombre": "Ana", # < 4 chars
        "apellido": "Sánchez",
        "cargo": "Asesor Comercial",
        "email": _unique_email("val_name1"),
        "celular": "3001234567",
        "documento_identidad": "12345678",
        "ciudad": "Pereira",
        "password": "SecurePassword2026!"
    }
    # Name too short
    res = client.post("/api/auth/register", json=base_payload)
    assert res.status_code == 400
    assert "nombre debe tener al menos 4 caracteres" in res.json()["detail"]

    # Name with numbers
    payload_num = dict(base_payload)
    payload_num["nombre"] = "Carlos12"
    res = client.post("/api/auth/register", json=payload_num)
    assert res.status_code == 400
    assert "únicamente letras y espacios" in res.json()["detail"]

    # Apellido too short
    payload_ape_short = dict(base_payload)
    payload_ape_short["nombre"] = "Carlos"
    payload_ape_short["apellido"] = "Paz"
    res = client.post("/api/auth/register", json=payload_ape_short)
    assert res.status_code == 400
    assert "apellido debe tener al menos 4 caracteres" in res.json()["detail"]

    # Apellido with digits
    payload_ape_num = dict(base_payload)
    payload_ape_num["nombre"] = "Carlos"
    payload_ape_num["apellido"] = "Gómez9"
    res = client.post("/api/auth/register", json=payload_ape_num)
    assert res.status_code == 400
    assert "únicamente letras y espacios" in res.json()["detail"]


def test_registration_rejects_invalid_cargo():
    """Rechaza cargos con menos de 5 caracteres o caracteres extraños."""
    payload = {
        "nombre": "Gabriel",
        "apellido": "Rincón",
        "cargo": "Ases", # < 5 chars
        "email": _unique_email("val_cargo"),
        "celular": "3001234567",
        "documento_identidad": "12345678",
        "ciudad": "Bucaramanga",
        "password": "SecurePassword2026!"
    }
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 400
    assert "cargo debe tener al menos 5 caracteres" in res.json()["detail"]

    # Cargo with forbidden characters
    payload["cargo"] = "Asesor <Ventas>"
    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 400
    assert "El cargo contiene caracteres no permitidos" in res2.json()["detail"]


def test_registration_rejects_invalid_celular():
    """Rechaza números de celular que no tengan exactamente 10 dígitos."""
    bad_celulares = ["300123456", "30012345678", "300123456a", "123456789"]
    for bad_cel in bad_celulares:
        payload = {
            "nombre": "Gabriel",
            "apellido": "Rincón",
            "cargo": "Asesor de Ventas",
            "email": _unique_email("val_cel"),
            "celular": bad_cel,
            "documento_identidad": "12345678",
            "ciudad": "Bucaramanga",
            "password": "SecurePassword2026!"
        }
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 400
        assert "exactamente 10 dígitos" in res.json()["detail"]


def test_registration_rejects_invalid_cedula():
    """Rechaza cédulas con menos de 8 dígitos, más de 11 dígitos o no numéricas."""
    bad_cedulas = ["1234567", "123456789012", "12345678A"]
    for bad_ced in bad_cedulas:
        payload = {
            "nombre": "Gabriel",
            "apellido": "Rincón",
            "cargo": "Asesor de Ventas",
            "email": _unique_email("val_ced"),
            "celular": "3001234567",
            "documento_identidad": bad_ced,
            "ciudad": "Bucaramanga",
            "password": "SecurePassword2026!"
        }
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 400
        assert "entre 8 y 11 dígitos" in res.json()["detail"]


def test_registration_rejects_invalid_ciudad():
    """Rechaza ciudades vacías, con menos de 3 caracteres o con números."""
    bad_ciudades = ["", "  ", "BA", "Bogotá 123", "Cali!"]
    for bad_city in bad_ciudades:
        payload = {
            "nombre": "Gabriel",
            "apellido": "Rincón",
            "cargo": "Asesor de Ventas",
            "email": _unique_email("val_city"),
            "celular": "3001234567",
            "documento_identidad": "12345678",
            "ciudad": bad_city,
            "password": "SecurePassword2026!"
        }
        res = client.post("/api/auth/register", json=payload)
        assert res.status_code == 400
