import os
import sys
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import httpx
from fastapi.testclient import TestClient
from backend.email_service import send_password_reset_email_graph

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


def test_user_existing_and_smtp_success(setup_teardown, capsys, monkeypatch):
    user_info = setup_teardown
    email = user_info["email"]

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "autoform.soporte@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "mock_app_password_123")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "autoform.soporte@gmail.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "AutoForm PDF - Seguridad")

    with patch("backend.main.send_password_reset_email", return_value=True) as mock_send:
        res = client.post("/api/auth/forgot-password", json={"email": email})
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        assert mock_send.called

        out = capsys.readouterr().out
        assert "[RESET] request_received" in out
        assert "[RESET] user_found=true" in out
        assert "[RESET] smtp_configured=true" in out
        assert "host=True, port=True, user=True, password=True" in out
        assert "[RESET] email_sent=true" in out
        assert f"user={email}" not in out
        assert "mock_app_password_123" not in out


def test_user_unregistered_logs_and_blind_response(capsys):
    unregistered_email = f"unregistered.{uuid.uuid4().hex[:6]}@iaclatam.com"
    res = client.post("/api/auth/forgot-password", json={"email": unregistered_email})
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "instrucciones de acceso" in res.json()["message"]

    out = capsys.readouterr().out
    assert "[RESET] request_received" in out
    assert "[RESET] user_found=false" in out
    assert "[RESET] email_sent=true" not in out


def test_missing_smtp_configuration_logs_error_and_returns_blind_response(setup_teardown, capsys, monkeypatch):
    user_info = setup_teardown
    email = user_info["email"]

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "autoform.soporte@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "autoform.soporte@gmail.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "AutoForm PDF - Seguridad")

    res = client.post("/api/auth/forgot-password", json={"email": email})
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "instrucciones de acceso" in res.json()["message"]

    out = capsys.readouterr().out
    assert "[RESET] request_received" in out
    assert "[RESET] user_found=true" in out
    assert "[RESET] smtp_configured=false" in out
    assert "password=False" in out
    assert "[RESET] [SMTP_CONFIG_ERROR]" in out
    assert "SMTP_PASSWORD" in out
    assert "[RESET] smtp_send_failed: RuntimeError" in out
    assert "[RESET] email_sent=true" not in out


def test_gmail_smtp_exception_logs_safe_traceback_and_returns_blind_response(setup_teardown, capsys, monkeypatch):
    import smtplib
    user_info = setup_teardown
    email = user_info["email"]

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "autoform.soporte@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "valid_looking_password")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "autoform.soporte@gmail.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "AutoForm PDF - Seguridad")

    auth_error = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
    with patch("backend.main.send_password_reset_email", side_effect=auth_error):
        res = client.post("/api/auth/forgot-password", json={"email": email})
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        assert "instrucciones de acceso" in res.json()["message"]

        out = capsys.readouterr().out
        assert "[RESET] request_received" in out
        assert "[RESET] user_found=true" in out
        assert "[RESET] smtp_configured=true" in out
        assert "[RESET] smtp_send_failed: SMTPAuthenticationError" in out
        assert "Traceback" in out
        assert "[RESET] email_sent=true" not in out


def test_user_in_supabase_auth_without_commercial_profile(capsys, monkeypatch):
    orphan_id = str(uuid.uuid4())
    orphan_email = f"orphan.{uuid.uuid4().hex[:6]}@iaclatam.com"

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "autoform.soporte@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "mock_app_password_123")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "autoform.soporte@gmail.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "AutoForm PDF - Seguridad")

    # Confirm user does NOT exist in CommercialProfile
    db = SessionLocal()
    existing_cp = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(orphan_email)).first()
    assert existing_cp is None
    db.close()

    mock_user = MagicMock()
    mock_user.id = orphan_id
    mock_user.email = orphan_email
    mock_user.user_metadata = {"nombre": "Orphan", "apellido": "Commercial", "cargo": "Asesor"}
    mock_user.user = None

    mock_supabase_admin = MagicMock()
    mock_supabase_admin.auth.admin.list_users.return_value = [mock_user]
    mock_supabase_admin.auth.admin.get_user_by_id.return_value = mock_user

    captured_reset_link = []
    def mock_send(recipient_email, recipient_name, reset_link):
        captured_reset_link.append(reset_link)
        return True

    with patch("backend.main.get_supabase_admin_client", return_value=mock_supabase_admin), \
         patch("backend.main.send_password_reset_email", side_effect=mock_send):

        # 1. Solicitud de restablecimiento
        res = client.post("/api/auth/forgot-password", json={"email": orphan_email})
        assert res.status_code == 200
        assert res.json()["status"] == "success"

        out = capsys.readouterr().out
        assert "[RESET] request_received" in out
        assert "[RESET] user_found=true" in out
        assert "[RESET] email_sent=true" in out
        assert len(captured_reset_link) == 1

        reset_link = captured_reset_link[0]
        raw_token = reset_link.split("token=")[1]

        # 2. Verificación temprana del token (fallback a Supabase Auth)
        res_verify = client.get(f"/api/auth/verify-reset-token?token={raw_token}")
        assert res_verify.status_code == 200
        assert res_verify.json()["valid"] is True
        assert "@iaclatam.com" in res_verify.json()["masked_email"]

        # 3. Restablecimiento de contraseña
        new_password = "OrphanNewPassword2026!"
        res_reset = client.post("/api/auth/reset-password", json={
            "token": raw_token,
            "password": new_password
        })
        assert res_reset.status_code == 200
        assert "actualizada exitosamente" in res_reset.json()["message"]

        # Verificar que Supabase Auth fue invocado con el id correcto
        mock_supabase_admin.auth.admin.update_user_by_id.assert_called_once_with(
            orphan_id,
            {"password": new_password}
        )

        # Verificar que CommercialProfile fue sincronizado/creado posteriormente
        db = SessionLocal()
        created_cp = db.query(CommercialProfile).filter(CommercialProfile.id == orphan_id).first()
        assert created_cp is not None
        assert created_cp.email == orphan_email
        assert verify_password(new_password, created_cp.password_hash) is True

        # Limpiar
        db.query(PasswordResetToken).filter(PasswordResetToken.user_id == orphan_id).delete()
        db.query(CommercialProfile).filter(CommercialProfile.id == orphan_id).delete()
        db.commit()
        db.close()


def test_microsoft_graph_success(setup_teardown, capsys, monkeypatch):
    user_info = setup_teardown
    email = user_info["email"]

    monkeypatch.setenv("EMAIL_PROVIDER", "microsoft_graph")
    monkeypatch.setenv("MS_TENANT_ID", "tenant-test-123")
    monkeypatch.setenv("MS_CLIENT_ID", "client-test-456")
    monkeypatch.setenv("MS_CLIENT_SECRET", "secret-test-789")
    monkeypatch.setenv("MAIL_SENDER", "pablo.reyes@iaclatam.com")
    monkeypatch.setenv("MAIL_SENDER_NAME", "AutoForm PDF - Seguridad")

    def mock_post(url, **kwargs):
        url_str = str(url)
        if "oauth2/v2.0/token" in url_str:
            assert kwargs["data"]["client_id"] == "client-test-456"
            assert kwargs["data"]["client_secret"] == "secret-test-789"
            assert kwargs["data"]["grant_type"] == "client_credentials"
            return httpx.Response(200, json={"access_token": "mock-access-token-xyz", "expires_in": 3600}, request=httpx.Request("POST", url))
        elif "/users/pablo.reyes@iaclatam.com/sendMail" in url_str:
            assert kwargs["headers"]["Authorization"] == "Bearer mock-access-token-xyz"
            msg = kwargs["json"]["message"]
            assert msg["from"]["emailAddress"]["address"] == "pablo.reyes@iaclatam.com"
            assert msg["toRecipients"][0]["emailAddress"]["address"] == email
            assert "token=" in msg["body"]["content"]
            return httpx.Response(202, request=httpx.Request("POST", url))
        return httpx.Response(404, request=httpx.Request("POST", url))

    with patch.object(httpx.Client, "post", side_effect=mock_post):
        res = client.post("/api/auth/forgot-password", json={"email": email})
        assert res.status_code == 200
        assert res.json()["status"] == "success"

        out = capsys.readouterr().out
        assert "[RESET] request_received" in out
        assert "[RESET] user_found=true" in out
        assert "[RESET] provider=microsoft_graph" in out
        assert "[RESET] graph_configured=true" in out
        assert "tenant=True, client_id=True, secret=True, sender=True" in out
        assert "[RESET] email_sent=true" in out
        # Verificaciones estrictas de seguridad: sin secretos ni tokens en logs
        assert "secret-test-789" not in out
        assert "mock-access-token-xyz" not in out
        assert "/?token=" not in out


def test_microsoft_graph_missing_credentials(setup_teardown, capsys, monkeypatch):
    user_info = setup_teardown
    email = user_info["email"]

    monkeypatch.setenv("EMAIL_PROVIDER", "microsoft_graph")
    monkeypatch.setenv("MS_TENANT_ID", "tenant-test-123")
    monkeypatch.setenv("MS_CLIENT_ID", "client-test-456")
    monkeypatch.setenv("MS_CLIENT_SECRET", "")
    monkeypatch.setenv("MAIL_SENDER", "pablo.reyes@iaclatam.com")

    res = client.post("/api/auth/forgot-password", json={"email": email})
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "instrucciones de acceso" in res.json()["message"]

    out = capsys.readouterr().out
    assert "[RESET] request_received" in out
    assert "[RESET] user_found=true" in out
    assert "[RESET] provider=microsoft_graph" in out
    assert "[RESET] graph_configured=false" in out
    assert "secret=False" in out
    assert "[RESET] [GRAPH_CONFIG_ERROR]" in out
    assert "MS_CLIENT_SECRET" in out
    assert "[RESET] graph_send_failed: RuntimeError" in out
    assert "[RESET] email_sent=true" not in out


def test_microsoft_graph_token_rejection(setup_teardown, capsys, monkeypatch):
    user_info = setup_teardown
    email = user_info["email"]

    monkeypatch.setenv("EMAIL_PROVIDER", "microsoft_graph")
    monkeypatch.setenv("MS_TENANT_ID", "tenant-test-123")
    monkeypatch.setenv("MS_CLIENT_ID", "client-test-456")
    monkeypatch.setenv("MS_CLIENT_SECRET", "invalid-secret-xyz")
    monkeypatch.setenv("MAIL_SENDER", "pablo.reyes@iaclatam.com")

    def mock_post(url, **kwargs):
        return httpx.Response(
            401,
            json={"error": "invalid_client", "error_description": "AADSTS7000215: Invalid client secret provided"},
            request=httpx.Request("POST", url)
        )

    with patch.object(httpx.Client, "post", side_effect=mock_post):
        res = client.post("/api/auth/forgot-password", json={"email": email})
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        assert "instrucciones de acceso" in res.json()["message"]

        out = capsys.readouterr().out
        assert "[RESET] request_received" in out
        assert "[RESET] user_found=true" in out
        assert "[RESET] provider=microsoft_graph" in out
        assert "[RESET] graph_configured=true" in out
        assert "[RESET] graph_send_failed: RuntimeError" in out
        assert "invalid_client" in out
        assert "invalid-secret-xyz" not in out
        assert "[RESET] email_sent=true" not in out


def test_microsoft_graph_sendmail_rejection(setup_teardown, capsys, monkeypatch):
    user_info = setup_teardown
    email = user_info["email"]

    monkeypatch.setenv("EMAIL_PROVIDER", "microsoft_graph")
    monkeypatch.setenv("MS_TENANT_ID", "tenant-test-123")
    monkeypatch.setenv("MS_CLIENT_ID", "client-test-456")
    monkeypatch.setenv("MS_CLIENT_SECRET", "valid-secret-123")
    monkeypatch.setenv("MAIL_SENDER", "pablo.reyes@iaclatam.com")

    def mock_post(url, **kwargs):
        url_str = str(url)
        if "oauth2/v2.0/token" in url_str:
            return httpx.Response(200, json={"access_token": "valid-token-abc", "expires_in": 3600}, request=httpx.Request("POST", url))
        elif "sendMail" in url_str:
            return httpx.Response(
                403,
                json={"error": {"code": "ErrorAccessDenied", "message": "Access is denied. Check permissions."}},
                request=httpx.Request("POST", url)
            )
        return httpx.Response(404, request=httpx.Request("POST", url))

    with patch.object(httpx.Client, "post", side_effect=mock_post):
        res = client.post("/api/auth/forgot-password", json={"email": email})
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        assert "instrucciones de acceso" in res.json()["message"]

        out = capsys.readouterr().out
        assert "[RESET] request_received" in out
        assert "[RESET] user_found=true" in out
        assert "[RESET] provider=microsoft_graph" in out
        assert "[RESET] graph_configured=true" in out
        assert "[RESET] graph_send_failed: RuntimeError" in out
        assert "ErrorAccessDenied" in out
        assert "valid-secret-123" not in out
        assert "[RESET] email_sent=true" not in out


def test_microsoft_graph_network_timeout(setup_teardown, capsys, monkeypatch):
    user_info = setup_teardown
    email = user_info["email"]

    monkeypatch.setenv("EMAIL_PROVIDER", "microsoft_graph")
    monkeypatch.setenv("MS_TENANT_ID", "tenant-test-123")
    monkeypatch.setenv("MS_CLIENT_ID", "client-test-456")
    monkeypatch.setenv("MS_CLIENT_SECRET", "valid-secret-123")
    monkeypatch.setenv("MAIL_SENDER", "pablo.reyes@iaclatam.com")

    with patch.object(httpx.Client, "post", side_effect=httpx.TimeoutException("Read timed out after 10.0s")):
        res = client.post("/api/auth/forgot-password", json={"email": email})
        assert res.status_code == 200
        assert res.json()["status"] == "success"
        assert "instrucciones de acceso" in res.json()["message"]

        out = capsys.readouterr().out
        assert "[RESET] graph_send_failed: RuntimeError" in out
        assert "Timeout" in out
        assert "[RESET] email_sent=true" not in out


def test_microsoft_graph_local_simulation(capsys, monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "local")
    monkeypatch.setenv("EMAIL_PROVIDER", "microsoft_graph")
    monkeypatch.setenv("MS_TENANT_ID", "")
    monkeypatch.setenv("MS_CLIENT_ID", "")
    monkeypatch.setenv("MS_CLIENT_SECRET", "")
    monkeypatch.setenv("MAIL_SENDER", "")

    result = send_password_reset_email_graph(
        recipient_email="local.user@iaclatam.com",
        recipient_name="Usuario Local",
        reset_link="http://localhost:5173/?token=simulated_token_123"
    )
    assert result is True

    out = capsys.readouterr().out
    assert "[DEV GRAPH EMAIL SIMULATION]" in out
    assert "l********r@iaclatam.com" in out
    assert "local.user@iaclatam.com" not in out



