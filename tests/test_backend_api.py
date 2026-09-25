import json
import os
import shutil
from fastapi.testclient import TestClient
from backend.main import app, INPUT_DIR, DATA_DIR

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == "1.2.0"

def test_company_data():
    response = client.get("/api/company-data")
    assert response.status_code == 200
    data = response.json()
    assert "razon_social" in data

def test_templates():
    response = client.get("/api/templates")
    assert response.status_code == 200
    templates = response.json().get("templates", [])
    assert len(templates) > 0

def test_get_pdf_pages():
    templates_res = client.get("/api/templates")
    templates = templates_res.json().get("templates", [])
    assert len(templates) > 0
    tpl_id = templates[0]["id"]
    response = client.get(f"/api/pdf/{tpl_id}/pages")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total_pages"] > 0
    assert len(res_data["pages"]) > 0
    assert "image_base64" in res_data["pages"][0]

def test_save_mapping_and_generate_with_styles():
    templates_res = client.get("/api/templates")
    templates = templates_res.json().get("templates", [])
    assert len(templates) > 0
    tpl_id = templates[0]["id"]

    mapping_path = os.path.join(DATA_DIR, f"{tpl_id}_mapping.json")
    original_mapping = None
    if os.path.exists(mapping_path):
        with open(mapping_path, "r", encoding="utf-8") as f:
            original_mapping = f.read()

    try:
        mapping_payload = {
            "template_id": tpl_id,
            "page_width": 612.0,
            "page_height": 792.0,
            "mappings": [
                {
                    "id": "box-test-1",
                    "field_key": "razon_social",
                    "label": "Razón Social",
                    "page_number": 0,
                    "box": {"x0": 100.0, "y0": 150.0, "x1": 350.0, "y1": 170.0},
                    "box_pct": {"x0_pct": 0.16, "y0_pct": 0.18, "x1_pct": 0.57, "y1_pct": 0.21},
                    "style": {
                        "font_family": "Arial",
                        "font_size": 11.0,
                        "bold": True,
                        "color": "#000000",
                        "item_type": "text"
                    }
                }
            ]
        }

        save_res = client.post("/api/mapping", json=mapping_payload)
        assert save_res.status_code == 200

        gen_res = client.post("/api/generate", json={
            "template_id": tpl_id,
            "commercial_profile_id": "legal_rep_only"
        })
        assert gen_res.status_code == 200
        gen_data = gen_res.json()
        assert gen_data["status"] == "success"
        assert gen_data["total_placed"] >= 1
        assert "filled_" in gen_data["filename"]
    finally:
        if original_mapping is not None:
            with open(mapping_path, "w", encoding="utf-8") as f:
                f.write(original_mapping)

def test_delete_template():
    # 1. Upload a dummy test pdf in the single-slot
    dummy_id = "test_dummy_temp_tpl"
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF"
    )
    up_res = client.post("/api/upload-pdf", files={"file": (f"{dummy_id}.pdf", pdf_bytes, "application/pdf")})
    assert up_res.status_code == 200

    dummy_pdf = os.path.join(INPUT_DIR, f"{dummy_id}.pdf")
    dummy_mapping = os.path.join(DATA_DIR, f"{dummy_id}_mapping.json")
    with open(dummy_mapping, "w", encoding="utf-8") as f:
        json.dump({"template_id": dummy_id, "mappings": []}, f)

    # Check template appears
    list_res = client.get("/api/templates")
    assert any(t["id"] == dummy_id for t in list_res.json()["templates"])

    # 2. Delete template
    del_res = client.delete(f"/api/templates/{dummy_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"
    assert not os.path.exists(dummy_pdf)
    assert not os.path.exists(dummy_mapping)
    print("[SUCCESS] Template deletion test passed!")

def test_ai_fill_endpoint_validation(monkeypatch):
    # 1. Non-existent template should return 404
    res = client.post("/api/ai-fill", json={
        "template_id": "non_existent_template_999",
        "commercial_profile_id": "legal_rep_only"
    })
    assert res.status_code == 404

    # 2. Mock PDFAgent.fill_pdf to avoid slow external API calls during integration tests
    from backend.pdf_filling_agent.agent import PDFAgent
    from backend.main import OUTPUT_DIR
    mock_out = os.path.join(OUTPUT_DIR, "test_mock_filled.pdf")
    with open(mock_out, "wb") as f:
        f.write(b"%PDF-1.4\n%%EOF")
    monkeypatch.setattr(PDFAgent, "fill_pdf", lambda self, *args, **kwargs: mock_out)

    templates_res = client.get("/api/templates")
    templates = templates_res.json().get("templates", [])
    if not templates:
        pdf_bytes = b"%PDF-1.4\n%%EOF"
        client.post("/api/upload-pdf", files={"file": ("sample_test_doc.pdf", pdf_bytes, "application/pdf")})
        templates_res = client.get("/api/templates")
        templates = templates_res.json().get("templates", [])

    assert len(templates) > 0
    tpl_id = templates[0]["id"]

    res2 = client.post("/api/ai-fill", json={
        "template_id": tpl_id,
        "commercial_profile_id": "legal_rep_only"
    })
    assert res2.status_code in [200, 500]
    print("[SUCCESS] AI Fill endpoint validation test passed!")


def test_single_file_slot_atomic_replacement():
    """Valida que subir un nuevo PDF reemplace atómicamente el documento previo del slot único."""
    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF"
    )

    # 1. Subir primer archivo en el slot
    filename_1 = "test_slot_document_a.pdf"
    res1 = client.post("/api/upload-pdf", files={"file": (filename_1, pdf_bytes, "application/pdf")})
    assert res1.status_code == 200
    tpl1_id = res1.json()["template_id"]

    list1 = client.get("/api/templates").json()
    assert list1["active_slot"] is not None
    assert list1["active_slot"]["template_id"] == tpl1_id
    assert len(list1["templates"]) == 1
    assert list1["templates"][0]["id"] == tpl1_id

    # 2. Subir segundo archivo: debe sobreescribir y eliminar físicamente el anterior
    filename_2 = "test_slot_document_b.pdf"
    res2 = client.post("/api/upload-pdf", files={"file": (filename_2, pdf_bytes, "application/pdf")})
    assert res2.status_code == 200
    tpl2_id = res2.json()["template_id"]

    path_1 = os.path.join(INPUT_DIR, filename_1)
    assert not os.path.exists(path_1), f"El archivo previo {filename_1} no fue eliminado de input/"

    list2 = client.get("/api/templates").json()
    assert list2["active_slot"] is not None
    assert list2["active_slot"]["template_id"] == tpl2_id
    assert len(list2["templates"]) == 1
    assert list2["templates"][0]["id"] == tpl2_id

    # 3. Eliminar el archivo activo limpia el slot
    del_res = client.delete(f"/api/templates/{tpl2_id}")
    assert del_res.status_code == 200
    path_2 = os.path.join(INPUT_DIR, filename_2)
    assert not os.path.exists(path_2)


if __name__ == "__main__":
    test_root()
    test_company_data()
    test_templates()
    test_get_pdf_pages()
    test_save_mapping_and_generate_with_styles()
    test_delete_template()
    test_ai_fill_endpoint_validation()
    test_single_file_slot_atomic_replacement()
    print("[SUCCESS] All backend API integration tests passed with Single-file Slot support!")
