import json
import os
import shutil
import pytest
import fitz
from fastapi.testclient import TestClient
from backend.main import app, DATA_DIR, INPUT_DIR, OUTPUT_DIR
from backend.auth_supabase import get_current_user

client = TestClient(app)

TEST_USER_ID = "53ac8522-38f6-46d8-86ee-1cad3d0b66c4"
TEST_COMPANY_ID = "8cb5378d-b9a7-4e2e-aa36-2718371731a6"

def get_test_pdf_bytes():
    doc = fitz.open()
    p = doc.new_page(-1, width=612, height=792)
    p.insert_text((72, 72), "Test PDF Mapping Persistence")
    b = doc.tobytes()
    doc.close()
    return b

@pytest.fixture(autouse=True)
def auth_override():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": TEST_USER_ID,
        "company_id": TEST_COMPANY_ID,
        "role": "admin",
        "email": "test.admin@iaclatam.com",
        "nombre": "Test Admin",
        "is_active": True
    }
    yield
    app.dependency_overrides.clear()

def test_empty_mapping_persistence_does_not_restore_legacy():
    pdf_bytes = get_test_pdf_bytes()
    tpl_filename = "persistence_empty_test.pdf"
    tpl_code = "persistence_empty_test"

    # Upload template
    up_res = client.post("/api/upload-pdf", files={"file": (tpl_filename, pdf_bytes, "application/pdf")})
    assert up_res.status_code == 200
    doc_id = up_res.json()["document_id"]

    # Create legacy mapping file simulating pre-existing default mapping
    legacy_file = os.path.join(DATA_DIR, f"{tpl_code}_mapping.json")
    user_file = os.path.join(DATA_DIR, f"{TEST_USER_ID}_{tpl_code}_mapping.json")
    user_uuid_file = os.path.join(DATA_DIR, f"{TEST_USER_ID}_{doc_id}_mapping.json")

    # Clean prior user files if any
    for uf in (user_file, user_uuid_file):
        if os.path.exists(uf):
            os.remove(uf)

    try:
        with open(legacy_file, "w", encoding="utf-8") as f:
            json.dump({
                "template_id": tpl_code,
                "page_width": 612,
                "page_height": 792,
                "mappings": [
                    {
                        "id": "box-leg-1",
                        "field_key": "razon_social",
                        "page_number": 0,
                        "box": {"x0": 100, "y0": 100, "x1": 200, "y1": 120}
                    }
                ]
            }, f)

        # First verify legacy is loaded if no user mapping exists
        get_res1 = client.get(f"/api/mapping/{tpl_code}")
        assert get_res1.status_code == 200
        assert len(get_res1.json().get("mappings", [])) == 1

        # Now user clears all fields and explicitly saves empty mapping
        save_res = client.post("/api/mapping", json={
            "template_id": tpl_code,
            "page_width": 612,
            "page_height": 792,
            "mappings": []
        })
        assert save_res.status_code == 200

        # Reload mapping by template_code: MUST return empty mapping, NOT the legacy one!
        get_res2 = client.get(f"/api/mapping/{tpl_code}")
        assert get_res2.status_code == 200
        assert get_res2.json().get("mappings") == []

        # Reload mapping by doc_id (UUID): MUST also return empty mapping!
        get_res3 = client.get(f"/api/mapping/{doc_id}")
        assert get_res3.status_code == 200
        assert get_res3.json().get("mappings") == []

    finally:
        # Cleanup
        client.delete(f"/api/templates/{tpl_code}")
        for p in (legacy_file, user_file, user_uuid_file):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

def test_generate_pdf_with_explicit_empty_mappings():
    pdf_bytes = get_test_pdf_bytes()
    tpl_filename = "gen_empty_test.pdf"
    tpl_code = "gen_empty_test"

    up_res = client.post("/api/upload-pdf", files={"file": (tpl_filename, pdf_bytes, "application/pdf")})
    assert up_res.status_code == 200
    doc_id = up_res.json()["document_id"]

    try:
        # Generate with empty mappings: MUST succeed with total_placed == 0
        gen_res = client.post("/api/generate", json={
            "template_id": tpl_code,
            "commercial_profile_id": "legal_rep_only",
            "mappings": []
        })
        assert gen_res.status_code == 200
        data = gen_res.json()
        assert data["status"] == "success"
        assert data["total_placed"] == 0
        assert "filled_" in data["filename"]
    finally:
        client.delete(f"/api/templates/{tpl_code}")

def test_empty_custom_text_does_not_fallback_to_company_data():
    pdf_bytes = get_test_pdf_bytes()
    tpl_filename = "custom_empty_text_test.pdf"
    tpl_code = "custom_empty_text_test"

    up_res = client.post("/api/upload-pdf", files={"file": (tpl_filename, pdf_bytes, "application/pdf")})
    assert up_res.status_code == 200

    try:
        # Send a mapping with custom_text == ""
        gen_res = client.post("/api/generate", json={
            "template_id": tpl_code,
            "commercial_profile_id": "legal_rep_only",
            "mappings": [
                {
                    "id": "box-empty-text",
                    "field_key": "razon_social",
                    "page_number": 0,
                    "box": {"x0": 50, "y0": 50, "x1": 150, "y1": 70},
                    "style": {
                        "custom_text": ""
                    }
                }
            ]
        })
        assert gen_res.status_code == 200
        data = gen_res.json()
        # Because custom_text was explicitly empty, 0 text placements should be stamped!
        assert data["total_placed"] == 0
    finally:
        client.delete(f"/api/templates/{tpl_code}")

def test_company_data_cleared_values_persistence():
    company_path = os.path.join(DATA_DIR, "company_data.json")
    original_data = None
    if os.path.exists(company_path):
        with open(company_path, "r", encoding="utf-8-sig") as f:
            original_data = f.read()

    try:
        # Fetch current data first
        curr_res = client.get("/api/company-data")
        assert curr_res.status_code == 200
        curr_data = curr_res.json()

        # Clear fields explicitly to empty strings
        cleared_payload = dict(curr_data)
        cleared_payload["razon_social"] = ""
        cleared_payload["nit"] = ""
        cleared_payload["ciudad"] = ""

        save_res = client.post("/api/company-data", json=cleared_payload)
        assert save_res.status_code == 200

        # Refetch: MUST remain empty strings and NOT restore defaults!
        refetch_res = client.get("/api/company-data")
        assert refetch_res.status_code == 200
        refetched = refetch_res.json()

        assert refetched["razon_social"] == ""
        assert refetched["nit"] == ""
        assert refetched["ciudad"] == ""

    finally:
        if original_data is not None:
            with open(company_path, "w", encoding="utf-8") as f:
                f.write(original_data)

def test_categorized_company_empty_persistence():
    cat_path = os.path.join(DATA_DIR, "categorized_company.json")
    original_cat = None
    if os.path.exists(cat_path):
        with open(cat_path, "r", encoding="utf-8-sig") as f:
            original_cat = f.read()

    try:
        empty_cat = {
            "id": [],
            "contacto": [],
            "banco": [],
            "financiero": [],
            "otros": []
        }
        save_res = client.post("/api/categorized-company", json=empty_cat)
        assert save_res.status_code == 200

        # Refetch: MUST return empty lists and NOT re-extract defaults!
        refetch_res = client.get("/api/categorized-company")
        assert refetch_res.status_code == 200
        refetched = refetch_res.json()

        assert refetched["id"] == []
        assert refetched["contacto"] == []
        assert refetched["banco"] == []
        assert refetched["financiero"] == []
        assert refetched["otros"] == []

    finally:
        if original_cat is not None:
            with open(cat_path, "w", encoding="utf-8") as f:
                f.write(original_cat)
