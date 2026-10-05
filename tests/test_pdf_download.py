import os
import time
import jwt
import fitz
import pytest
from fastapi.testclient import TestClient
from backend.main import app, OUTPUT_DIR
from backend.auth_supabase import EXPECTED_ISSUER, SUPABASE_SERVICE_ROLE_KEY
from backend.db.session import SessionLocal
from backend.db.models import CommercialProfile

client = TestClient(app)

KELLY_AUTH_SUB = "c3a6cee5-63b1-4c3f-8550-e9c86eac8987"
CARLOS_AUTH_SUB = "11111111-1111-4111-8111-111111111111"
COMPANY_ID = "8cb5378d-b9a7-4e2e-aa36-2718371731a6"

def create_mock_jwt(sub: str, email: str, role: str = "commercial"):
    now = int(time.time())
    payload = {
        "sub": sub,
        "aud": "authenticated",
        "role": "authenticated",
        "email": email,
        "iss": EXPECTED_ISSUER,
        "iat": now,
        "exp": now + 3600,
        "app_metadata": {
            "company_id": COMPANY_ID,
            "role": role
        },
        "user_metadata": {
            "nombre": email.split("@")[0]
        }
    }
    return jwt.encode(payload, SUPABASE_SERVICE_ROLE_KEY or "test_secret_key_1234567890123456", algorithm="HS256")

TOKEN_KELLY = create_mock_jwt(KELLY_AUTH_SUB, "Kelly.Delgado@iaclatam.com", "commercial")
TOKEN_CARLOS = create_mock_jwt(CARLOS_AUTH_SUB, "carlos@iaclatam.com", "commercial")

def test_download_pdf_success_and_isolation():
    # 1. Asegurar que existe el perfil de Kelly en CommercialProfile
    db = SessionLocal()
    try:
        prof = db.query(CommercialProfile).filter(CommercialProfile.id == "prof-kelly-delgado").first()
        if not prof:
            prof = CommercialProfile(
                id="prof-kelly-delgado",
                email="Kelly.Delgado@iaclatam.com",
                nombre="Kelly",
                apellido="Delgado",
                is_active=True,
                role="commercial"
            )
            db.add(prof)
            db.commit()
    finally:
        db.close()

    # 2. Crear un archivo PDF en la carpeta de Kelly (prof-kelly-delgado)
    kelly_out_dir = os.path.join(OUTPUT_DIR, "prof-kelly-delgado")
    os.makedirs(kelly_out_dir, exist_ok=True)
    pdf_filename = "filled_test_isagen_download.pdf"
    pdf_path = os.path.join(kelly_out_dir, pdf_filename)
    
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Formulario de Inscripcion Diligenciado")
    doc.save(pdf_path)
    doc.close()

    try:
        # 3. Descarga NO autenticada -> 401 Unauthorized
        res_no_auth = client.get(f"/api/download/{pdf_filename}")
        assert res_no_auth.status_code == 401
        assert "autenticación" in res_no_auth.json()["detail"].lower()

        # 4. Descarga por Kelly usando Header Bearer -> 200 OK con Content-Type application/pdf
        res_kelly_header = client.get(
            f"/api/download/{pdf_filename}",
            headers={"Authorization": f"Bearer {TOKEN_KELLY}"}
        )
        assert res_kelly_header.status_code == 200
        assert "application/pdf" in res_kelly_header.headers.get("content-type", "")
        assert len(res_kelly_header.content) > 100

        # 5. Descarga por Kelly usando query parameter ?token=... (simulando clic de navegador) -> 200 OK
        res_kelly_query = client.get(
            f"/api/download/{pdf_filename}?token={TOKEN_KELLY}"
        )
        assert res_kelly_query.status_code == 200
        assert "application/pdf" in res_kelly_query.headers.get("content-type", "")
        assert len(res_kelly_query.content) > 100

        # 6. Descarga por otro usuario (Carlos) -> 403 Forbidden (estricto aislamiento)
        res_carlos = client.get(
            f"/api/download/{pdf_filename}",
            headers={"Authorization": f"Bearer {TOKEN_CARLOS}"}
        )
        assert res_carlos.status_code == 403
        assert "otro usuario" in res_carlos.json()["detail"].lower()

        # 7. Descarga por Carlos con query param -> 403 Forbidden
        res_carlos_param = client.get(
            f"/api/download/{pdf_filename}?token={TOKEN_CARLOS}"
        )
        assert res_carlos_param.status_code == 403

    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
