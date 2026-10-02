import os
import uuid
import pytest
import fitz
from fastapi.testclient import TestClient
import time
import jwt
from backend.main import app, INPUT_DIR, DATA_DIR, OUTPUT_DIR
from backend.auth_supabase import get_current_user, EXPECTED_ISSUER, SUPABASE_SERVICE_ROLE_KEY

client = TestClient(app)

USER_A_ID = "11111111-1111-4111-8111-111111111111"
USER_B_ID = "22222222-2222-4222-8222-222222222222"
ADMIN_C_ID = "33333333-3333-4333-8333-333333333333"
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

TOKEN_A = create_mock_jwt(USER_A_ID, "carlos@iaclatam.com", "commercial")
TOKEN_B = create_mock_jwt(USER_B_ID, "kelly@iaclatam.com", "commercial")
TOKEN_C = create_mock_jwt(ADMIN_C_ID, "admin.c@iaclatam.com", "admin")

current_auth_user = None

def mock_get_current_user():
    return current_auth_user

@pytest.fixture(autouse=True)
def auth_mock():
    global current_auth_user
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.clear()

def generate_pdf_bytes():
    doc = fitz.open()
    p = doc.new_page(-1, width=612, height=792)
    p.insert_text((72, 72), "Document Isolation Test PDF Content")
    b = doc.tobytes()
    doc.close()
    return b

def test_cross_user_document_isolation():
    global current_auth_user

    # =========================================================================
    # Phase 1: User A (Carlos) uploads a sensitive PDF document
    # =========================================================================
    current_auth_user = {
        "id": USER_A_ID,
        "company_id": COMPANY_ID,
        "role": "commercial",
        "email": "carlos@iaclatam.com",
        "nombre": "Carlos Perez",
        "is_active": True,
        "token": TOKEN_A
    }

    pdf_bytes = generate_pdf_bytes()
    upload_res = client.post(
        "/api/upload-pdf",
        files={"file": ("carlos_sensitive_contract.pdf", pdf_bytes, "application/pdf")}
    )
    assert upload_res.status_code == 200, upload_res.text
    doc_a_id = upload_res.json()["document_id"]
    template_a_id = upload_res.json()["template_id"]

    # Storage path must be uniquely isolated and partitioned (user_documents/<user_id>/<uuid>.pdf)
    assert doc_a_id is not None
    user_cache = os.path.join(INPUT_DIR, USER_A_ID, f"{doc_a_id}.pdf")
    assert os.path.exists(user_cache), f"User A cache not found at {user_cache}"

    # User A lists templates -> MUST see the uploaded document
    list_a = client.get("/api/templates")
    assert list_a.status_code == 200
    a_templates = list_a.json().get("templates", [])
    assert len(a_templates) == 1
    assert a_templates[0]["document_id"] == doc_a_id

    # User A previews PDF pages -> 200 OK
    pages_a = client.get(f"/api/pdf/{doc_a_id}/pages")
    assert pages_a.status_code == 200
    assert len(pages_a.json()["pages"]) > 0

    # User A creates a mapping for this document
    save_map_a = client.post("/api/mapping", json={
        "template_id": doc_a_id,
        "page_width": 612.0,
        "page_height": 792.0,
        "mappings": []
    })
    assert save_map_a.status_code == 200

    # User A can get their mapping
    get_map_a = client.get(f"/api/mapping/{doc_a_id}")
    assert get_map_a.status_code == 200

    # User A generates a filled PDF
    gen_a = client.post("/api/generate", json={
        "template_id": doc_a_id,
        "commercial_profile_id": "legal_rep_only",
        "mappings": [
            {
                "id": "box-1",
                "field_key": "razon_social",
                "page_number": 0,
                "box": {"x0": 100, "y0": 100, "x1": 200, "y1": 120}
            }
        ]
    })
    assert gen_a.status_code == 200

    # User A can download their document
    dl_a = client.get(f"/api/download/{doc_a_id}", headers={"Authorization": f"Bearer {TOKEN_A}"})
    assert dl_a.status_code in [200, 307]

    # =========================================================================
    # Phase 2: User B (Kelly) logs in (different account, same company)
    # =========================================================================
    current_auth_user = {
        "id": USER_B_ID,
        "company_id": COMPANY_ID,
        "role": "commercial",
        "email": "kelly@iaclatam.com",
        "nombre": "Kelly Delgado",
        "is_active": True,
        "token": TOKEN_B
    }

    # 1. User B lists templates -> Carlos's document MUST NOT appear
    list_b = client.get("/api/templates")
    assert list_b.status_code == 200
    b_templates = list_b.json().get("templates", [])
    assert len(b_templates) == 0, f"Cross-account leak: User B sees User A's templates: {b_templates}"
    assert list_b.json().get("active_slot") is None

    # 2. User B attempts preview on User A's document -> MUST return 403 Forbidden
    pages_b = client.get(f"/api/pdf/{doc_a_id}/pages")
    assert pages_b.status_code == 403, f"Expected 403 Forbidden on preview, got {pages_b.status_code}"

    # 3. User B attempts deletion of User A's document -> MUST return 403 Forbidden
    del_b = client.delete(f"/api/templates/{doc_a_id}")
    assert del_b.status_code == 403, f"Expected 403 Forbidden on delete, got {del_b.status_code}"

    # 4. User B attempts to generate PDF from User A's document -> MUST return 403 Forbidden
    gen_b = client.post("/api/generate", json={
        "template_id": doc_a_id,
        "commercial_profile_id": "legal_rep_only"
    })
    assert gen_b.status_code == 403, f"Expected 403 Forbidden on generate, got {gen_b.status_code}"

    # 5. User B attempts AI-fill on User A's document -> MUST return 403 Forbidden
    ai_b = client.post("/api/ai-fill", json={
        "template_id": doc_a_id,
        "commercial_profile_id": "legal_rep_only"
    })
    assert ai_b.status_code == 403, f"Expected 403 Forbidden on ai-fill, got {ai_b.status_code}"

    # 6. User B attempts to access User A's mapping -> MUST return 403 Forbidden
    get_map_b = client.get(f"/api/mapping/{doc_a_id}")
    assert get_map_b.status_code == 403, f"Expected 403 Forbidden on mapping get, got {get_map_b.status_code}"

    # 7. User B attempts to overwrite User A's mapping -> MUST return 403 Forbidden
    save_map_b = client.post("/api/mapping", json={
        "template_id": doc_a_id,
        "page_width": 612.0,
        "page_height": 792.0,
        "mappings": []
    })
    assert save_map_b.status_code == 403, f"Expected 403 Forbidden on mapping save, got {save_map_b.status_code}"

    # 8. User B attempts to download User A's document -> MUST return 403 Forbidden
    dl_b = client.get(f"/api/download/{doc_a_id}", headers={"Authorization": f"Bearer {TOKEN_B}"})
    assert dl_b.status_code == 403, f"Expected 403 Forbidden on download, got {dl_b.status_code}"

    # =========================================================================
    # Phase 3: Admin User C logs in (Admin role must NOT hijack other users' documents)
    # =========================================================================
    current_auth_user = {
        "id": ADMIN_C_ID,
        "company_id": COMPANY_ID,
        "role": "admin",
        "email": "admin.c@iaclatam.com",
        "nombre": "Admin Boss",
        "is_active": True,
        "token": TOKEN_C
    }

    # Admin C listing must NOT return Carlos's personal active document
    list_c = client.get("/api/templates")
    assert list_c.status_code == 200
    c_templates = list_c.json().get("templates", [])
    assert len(c_templates) == 0, f"Cross-account leak: Admin C sees User A's templates: {c_templates}"

    # Admin C accessing Carlos's document without company sharing -> 403 Forbidden
    pages_c = client.get(f"/api/pdf/{doc_a_id}/pages")
    assert pages_c.status_code == 403, f"Expected 403 Forbidden for admin accessing other user doc, got {pages_c.status_code}"

    # Admin C downloading Carlos's document without company sharing -> 403 Forbidden
    dl_c = client.get(f"/api/download/{doc_a_id}", headers={"Authorization": f"Bearer {TOKEN_C}"})
    assert dl_c.status_code == 403, f"Expected 403 Forbidden for admin downloading other user doc, got {dl_c.status_code}"
