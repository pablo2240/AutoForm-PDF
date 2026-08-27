import json
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["version"] == "1.1.0"

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
    response = client.get("/api/pdf/formato_conocimiento/pages")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["total_pages"] > 0
    assert len(res_data["pages"]) > 0
    assert "image_base64" in res_data["pages"][0]

def test_save_mapping_and_generate_with_styles():
    mapping_payload = {
        "template_id": "formato_conocimiento",
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
    
    gen_res = client.post("/api/generate", json={"template_id": "formato_conocimiento"})
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["status"] == "success"
    assert gen_data["total_placed"] >= 1
    assert "filled_formato_conocimiento.pdf" in gen_data["filename"]

if __name__ == "__main__":
    test_root()
    test_company_data()
    test_templates()
    test_get_pdf_pages()
    test_save_mapping_and_generate_with_styles()
    print("[SUCCESS] All backend API integration tests passed with new styles support!")
