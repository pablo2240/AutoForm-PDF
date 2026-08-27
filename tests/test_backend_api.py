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
    response = client.get("/api/pdf/formulario_datos_empresa/pages")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total_pages"] > 0
    assert len(res_data["pages"]) > 0
    assert "image_base64" in res_data["pages"][0]

def test_save_mapping_and_generate_with_styles():
    mapping_payload = {
        "template_id": "formulario_datos_empresa",
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
    
    gen_res = client.post("/api/generate", json={"template_id": "formulario_datos_empresa"})
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["status"] == "success"
    assert gen_data["total_placed"] >= 1
    assert "filled_formulario_datos_empresa.pdf" in gen_data["filename"]

def test_delete_template():
    # 1. Create a dummy test pdf in input/
    dummy_id = "test_dummy_temp_tpl"
    dummy_pdf = os.path.join(INPUT_DIR, f"{dummy_id}.pdf")
    with open(dummy_pdf, "wb") as f:
        # Create minimal PDF bytes
        f.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF")
    
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

if __name__ == "__main__":
    test_root()
    test_company_data()
    test_templates()
    test_get_pdf_pages()
    test_save_mapping_and_generate_with_styles()
    test_delete_template()
    print("[SUCCESS] All backend API integration tests passed with template deletion and temporary session support!")
