import os
import sys
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["APP_ENVIRONMENT"] = "test"

from backend.main import app, forgot_password_rate_limiter
from backend.db.models import Base, CommercialProfile, PasswordResetToken
from backend.db.session import engine, SessionLocal
from backend.db.auth import hash_password, verify_password

# Ensure schema exists in test database
Base.metadata.create_all(bind=engine)

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    forgot_password_rate_limiter.reset()

    # Create a test commercial user
    db = SessionLocal()
    test_user_id = str(uuid.uuid4())
    test_email = f"reset.test.{uuid.uuid4().hex[:6]}@iaclatam.com"
    initial_pass = "InitialPass123!"
    user = CommercialProfile(
        id=test_user_id,
        profile_name="Test User Reset",
        nombre="Usuario",
        apellido="Prueba",
        cargo="Asesor Comercial",
        email=test_email,
        celular="3001234567",
        ciudad="Bogota",
        tipo_documento="CC",
        documento_identidad="12345678",
        role="commercial",
        password_hash=hash_password(initial_pass),
        is_active=True
    )
    db.add(user)
    db.commit()

    yield {
        "user_id": test_user_id,
        "email": test_email,
        "initial_pass": initial_pass
    }

    # Clean up test rows
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == test_user_id).delete()
    db.query(CommercialProfile).filter(CommercialProfile.id == test_user_id).delete()
    db.commit()
    db.close()

def test_forgot_password_blind_response_for_nonexistent_email():
    res = client.post("/api/auth/forgot-password", json={"email": "nonexistent.user@iaclatam.com"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "instrucciones de acceso" in data["message"]

def test_forgot_password_rate_limiting():
    # Max 3 attempts allowed
    for _ in range(3):
        res = client.post("/api/auth/forgot-password", json={"email": "user@iaclatam.com"})
        assert res.status_code == 200

    # 4th attempt should be blocked with 429
    res = client.post("/api/auth/forgot-password", json={"email": "user@iaclatam.com"})
    assert res.status_code == 429
    assert "Límite de solicitudes" in res.json()["detail"]

def test_forgot_password_generates_token_and_sends_email(setup_teardown):
    user_info = setup_teardown
    email = user_info["email"]

    with patch("backend.main.send_password_reset_email") as mock_send:
        mock_send.return_value = True
        res = client.post("/api/auth/forgot-password", json={"email": email})
        assert res.status_code == 200
        assert mock_send.called
        call_args = mock_send.call_args[1]
        assert call_args["recipient_email"] == email
        reset_link = call_args["reset_link"]
        assert "token=" in reset_link

        # Verify token in DB
        db = SessionLocal()
        tokens = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_info["user_id"]).all()
        assert len(tokens) == 1
        raw_token = reset_link.split("token=")[1]
        expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        assert tokens[0].token_hash == expected_hash
        assert tokens[0].used_at is None
        db.close()

def test_verify_reset_token_lifecycle(setup_teardown):
    user_info = setup_teardown
    db = SessionLocal()
    raw_token = "valid_token_test_1234567890abcdef"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    rec = PasswordResetToken(
        id=str(uuid.uuid4()),
        user_id=user_info["user_id"],
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        request_ip="127.0.0.1"
    )
    db.add(rec)
    db.commit()

    # 1. Valid token
    res = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
    assert res.status_code == 200
    assert res.json()["valid"] is True
    assert "@iaclatam.com" in res.json()["masked_email"]

    # 2. Invalid token
    res_bad = client.get("/api/auth/verify-reset-token?token=completely_invalid_token_123")
    assert res_bad.status_code == 400

    # 3. Expired token
    rec.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    res_exp = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
    assert res_exp.status_code == 400
    assert "ha expirado" in res_exp.json()["detail"]

    # 4. Already used token
    rec.expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    rec.used_at = datetime.now(timezone.utc)
    db.commit()
    res_used = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
    assert res_used.status_code == 400
    assert "ya ha sido utilizado" in res_used.json()["detail"]
    db.close()

def test_reset_password_dual_sync_and_single_use(setup_teardown):
    user_info = setup_teardown
    db = SessionLocal()
    raw_token = "secure_reset_token_test_for_execution_1234567"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    rec = PasswordResetToken(
        id=str(uuid.uuid4()),
        user_id=user_info["user_id"],
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        request_ip="127.0.0.1"
    )
    db.add(rec)
    db.commit()

    mock_supabase_admin = MagicMock()
    with patch("backend.main.get_supabase_admin_client", return_value=mock_supabase_admin):
        # 1. Reject weak password
        res_weak = client.post("/api/auth/reset-password", json={
            "token": raw_token,
            "password": "weak"
        })
        assert res_weak.status_code == 400
        assert "al menos 8 caracteres" in res_weak.json()["detail"]

        # 2. Execute successful reset with strong password
        new_password = "BrandNewSecurePass2026!"
        res_ok = client.post("/api/auth/reset-password", json={
            "token": raw_token,
            "password": new_password
        })
        assert res_ok.status_code == 200
        assert "actualizada exitosamente" in res_ok.json()["message"]

        # Verify Supabase Auth admin was invoked
        mock_supabase_admin.auth.admin.update_user_by_id.assert_called_once_with(
            user_info["user_id"],
            {"password": new_password}
        )

        # Verify local relational password_hash was updated
        db.expire_all()
        updated_user = db.query(CommercialProfile).filter(CommercialProfile.id == user_info["user_id"]).first()
        assert verify_password(new_password, updated_user.password_hash) is True
        assert verify_password(user_info["initial_pass"], updated_user.password_hash) is False

        # Verify token is marked as consumed (One-Time Use)
        updated_token = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()
        assert updated_token.used_at is not None

        # 3. Second attempt with the same token must fail
        res_reuse = client.post("/api/auth/reset-password", json={
            "token": raw_token,
            "password": "AnotherNewPassword2026!"
        })
        assert res_reuse.status_code == 400
        assert "inválido o ya ha sido utilizado" in res_reuse.json()["detail"]

    db.close()
