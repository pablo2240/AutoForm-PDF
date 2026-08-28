import os
import sys
import json
import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.pdf_filling_agent.visual_processor import VisualPDFProcessor, VisualPlacement

app = FastAPI(title="AutoForm PDF API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
INPUT_DIR = os.path.join(PROJECT_ROOT, "input")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

class ItemStyle(BaseModel):
    font_family: Optional[str] = "Arial"
    font_size: Optional[float] = 10.0
    bold: Optional[bool] = False
    color: Optional[str] = "#000000"
    align: Optional[str] = "left"
    custom_text: Optional[str] = None
    image_base64: Optional[str] = None
    item_type: Optional[str] = "text"

class MappingItem(BaseModel):
    id: Optional[str] = None
    field_key: str
    label: Optional[str] = ""
    page_number: int  # 0-indexed
    box: Dict[str, float]  # x0, y0, x1, y1 (in PDF points)
    box_pct: Optional[Dict[str, float]] = None # x0_pct, y0_pct, x1_pct, y1_pct (0 to 1)
    style: Optional[ItemStyle] = None

class TemplateMapping(BaseModel):
    template_id: str
    page_width: float
    page_height: float
    mappings: List[MappingItem]

class GenerateRequest(BaseModel):
    template_id: str
    mappings: Optional[List[MappingItem]] = None
    is_temporary: Optional[bool] = False

class AiFillRequest(BaseModel):
    template_id: str


def hex_to_rgb_tuple(hex_color: Optional[str]) -> Tuple[float, float, float]:
    """Convert hex color (#000000) to normalized RGB float tuple (0.0 to 1.0)."""
    if not hex_color or not hex_color.startswith("#") or len(hex_color) < 7:
        return (0.0, 0.0, 0.0)
    try:
        h = hex_color.lstrip("#")
        r, g, b = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        return (round(r / 255.0, 3), round(g / 255.0, 3), round(b / 255.0, 3))
    except Exception:
        return (0.0, 0.0, 0.0)

@app.get("/")
def read_root():
    return {"message": "AutoForm PDF API is running", "version": "1.2.0"}

@app.get("/api/company-data")
def get_company_data():
    path = os.path.join(DATA_DIR, "company_data.json")
    if not os.path.exists(path):
        default_data = {
            "razon_social": "Ingeniería Asistida Por Computador S.A.S",
            "nit": "8110047212",
            "representante_legal": "Guillermo Humberto Cañón Sarria",
            "representante_nombre": "Guillermo Humberto",
            "representante_apellido": "Cañón Sarria",
            "tipo_documento": "C.C",
            "numero_cedula": "98555384",
            "lugar_expedicion_rep": "Envigado",
            "correo_rep": "guillermo.canon@iaclatam.com",
            "celular_rep": "3104120217",
            "ciudad": "Medellin",
            "departamento": "Antioquia",
            "pais": "Colombia",
            "telefono": "2656868",
            "direccion_principal": "Carrera 63 B # 32 E -25 OFC 206",
            "pagina_web": "iaclatam.com",
            "entidad_bancaria": "BANCOLOMBIA",
            "numero_cuenta": "00300833888",
            "tipo_cuenta": "Ahorros"
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2)
        return default_data
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/company-data")
def update_company_data(data: Dict[str, Any]):
    path = os.path.join(DATA_DIR, "company_data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return {"status": "success", "message": "Company data saved successfully"}

@app.get("/api/templates")
def list_templates():
    templates = []
    if os.path.exists(INPUT_DIR):
        for f in os.listdir(INPUT_DIR):
            if f.lower().endswith(".pdf"):
                template_id = os.path.splitext(f)[0]
                size_kb = round(os.path.getsize(os.path.join(INPUT_DIR, f)) / 1024, 1)
                templates.append({
                    "id": template_id,
                    "filename": f,
                    "size_kb": size_kb
                })
    return {"templates": templates}

@app.post("/api/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se admiten archivos PDF")
    dest_path = os.path.join(INPUT_DIR, file.filename)
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    template_id = os.path.splitext(file.filename)[0]
    return {
        "status": "success",
        "template_id": template_id,
        "filename": file.filename
    }

@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str):
    deleted_files = []
    
    # Remove PDF candidates from input/
    pdf_candidates = [
        os.path.join(INPUT_DIR, f"{template_id}.pdf"),
        os.path.join(INPUT_DIR, template_id)
    ]
    for p in pdf_candidates:
        if os.path.exists(p):
            try:
                os.remove(p)
                deleted_files.append(os.path.basename(p))
            except Exception as e:
                print(f"[ERROR] Removing PDF {p}: {e}")

    # Remove mapping JSON from backend/data/
    map_path = os.path.join(DATA_DIR, f"{template_id}_mapping.json")
    if os.path.exists(map_path):
        try:
            os.remove(map_path)
            deleted_files.append(os.path.basename(map_path))
        except Exception as e:
            print(f"[ERROR] Removing mapping {map_path}: {e}")

    if not deleted_files:
        raise HTTPException(status_code=404, detail=f"Plantilla '{template_id}' no encontrada en el sistema")

    return {
        "status": "success",
        "message": f"Plantilla '{template_id}' eliminada exitosamente",
        "deleted": deleted_files
    }

@app.get("/api/pdf/{template_id}/pages")
def get_pdf_pages(template_id: str):
    pdf_path = os.path.join(INPUT_DIR, f"{template_id}.pdf")
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(INPUT_DIR, template_id)
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail=f"PDF '{template_id}' not found in input/")
    
    processor = VisualPDFProcessor(output_dir=OUTPUT_DIR, dpi=120)
    pages = processor.render_all_pages(pdf_path, dpi=120)
    
    return {
        "template_id": template_id,
        "total_pages": len(pages),
        "pages": [
            {
                "page_num": p.page,
                "width_px": p.width_px,
                "height_px": p.height_px,
                "page_width_pts": p.page_width_pts,
                "page_height_pts": p.page_height_pts,
                "image_base64": f"data:image/png;base64,{p.image_base64}"
            }
            for p in pages
        ]
    }

@app.post("/api/mapping")
def save_mapping(mapping: TemplateMapping):
    path = os.path.join(DATA_DIR, f"{mapping.template_id}_mapping.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(mapping.model_dump_json(indent=2))
    return {"status": "success", "message": "Mapping saved successfully"}

@app.get("/api/mapping/{template_id}")
def get_mapping(template_id: str):
    path = os.path.join(DATA_DIR, f"{template_id}_mapping.json")
    if not os.path.exists(path):
        return {"template_id": template_id, "page_width": 0, "page_height": 0, "mappings": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/api/generate")
def generate_pdf(req: GenerateRequest):
    # 1. Load company data
    company_data_path = os.path.join(DATA_DIR, "company_data.json")
    if not os.path.exists(company_data_path):
        raise HTTPException(status_code=404, detail="Company data not found")
    with open(company_data_path, "r", encoding="utf-8") as f:
        company_data = json.load(f)

    # 2. Get mappings (from request or from saved JSON)
    mappings = []
    if req.mappings is not None and len(req.mappings) > 0:
        mappings = [m.model_dump() for m in req.mappings]
    else:
        mapping_path = os.path.join(DATA_DIR, f"{req.template_id}_mapping.json")
        if not os.path.exists(mapping_path):
            raise HTTPException(status_code=404, detail=f"No mappings found for template {req.template_id}")
        with open(mapping_path, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)
            mappings = mapping_data.get("mappings", [])

    # 3. Locate input PDF
    pdf_path = os.path.join(INPUT_DIR, f"{req.template_id}.pdf")
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(INPUT_DIR, req.template_id)
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail=f"Input PDF '{req.template_id}' not found")

    # 4. Create visual placements
    placements = []
    for item in mappings:
        field_key = item["field_key"]
        style = item.get("style", {}) or {}
        item_type = style.get("item_type", "text")
        
        box = item["box"]
        rect = [box["x0"], box["y0"], box["x1"], box["y1"]]

        if item_type == "image" and style.get("image_base64"):
            placements.append(
                VisualPlacement(
                    page=item["page_number"],
                    rect=rect,
                    item_type="image",
                    image_base64=style.get("image_base64"),
                    field_description=item.get("label", "Imagen / Firma")
                )
            )
        else:
            custom_text = style.get("custom_text")
            if custom_text is not None and custom_text != "":
                value = custom_text
            else:
                value = company_data.get(field_key, "")

            if value:
                font_fam = style.get("font_family", "Arial")
                font_size = float(style.get("font_size") or 10.0)
                bold = bool(style.get("bold", False))
                color_rgb = hex_to_rgb_tuple(style.get("color", "#000000"))

                align = style.get("align", "left") or "left"
                placements.append(
                    VisualPlacement(
                        page=item["page_number"],
                        rect=rect,
                        text=str(value),
                        font_size=font_size,
                        font_family=font_fam,
                        bold=bold,
                        color_rgb=color_rgb,
                        align=align,
                        item_type="text",
                        field_description=item.get("label", field_key)
                    )
                )

    if not placements:
        raise HTTPException(status_code=400, detail="No matching fields or images to place onto PDF")

    processor = VisualPDFProcessor(output_dir=OUTPUT_DIR)
    out_filename = f"filled_{os.path.basename(pdf_path)}"
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    processor.apply_visual_placements(pdf_path, placements, output_path=out_path)

    # 5. If temporary session requested, cleanup base template and mapping
    if req.is_temporary:
        try:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
            mapping_path = os.path.join(DATA_DIR, f"{req.template_id}_mapping.json")
            if os.path.exists(mapping_path):
                os.remove(mapping_path)
        except Exception as e:
            print(f"[WARNING] Temporary cleanup warning: {e}")

    return {
        "status": "success",
        "filename": out_filename,
        "download_url": f"/api/download/{out_filename}",
        "total_placed": len(placements),
        "is_temporary": req.is_temporary
    }

@app.post("/api/ai-fill")
def ai_fill_pdf(req: AiFillRequest):
    # 1. Locate input PDF
    template_id = req.template_id
    pdf_path = os.path.join(INPUT_DIR, f"{template_id}.pdf")
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(INPUT_DIR, template_id)
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail=f"Input PDF '{template_id}' not found")

    # 2. Load company data
    company_data_path = os.path.join(DATA_DIR, "company_data.json")
    if not os.path.exists(company_data_path):
        raise HTTPException(status_code=404, detail="Company data not found")
    with open(company_data_path, "r", encoding="utf-8") as f:
        company_data = json.load(f)

    instructions = (
        "Por favor llena este formulario PDF con los datos principales de la empresa:\n"
        f"{json.dumps(company_data, ensure_ascii=False, indent=2)}\n\n"
        "Incluye datos de identificación (NIT, Razón Social, Representante Legal, Cédula), "
        "datos de contacto (Ciudad, Dirección, Correo, Celular, Teléfono) y "
        "datos bancarios (Banco, Tipo de cuenta, Número de cuenta) en los campos correspondientes."
    )

    try:
        from backend.pdf_filling_agent.agent import PDFAgent
        # ponytail: instantiates PDFAgent per request.
        agent = PDFAgent(company_profile_path=company_data_path)
        output_path = agent.fill_pdf(pdf_path, instructions, output_dir=OUTPUT_DIR, mode="auto")
        out_filename = os.path.basename(output_path)

        return {
            "status": "success",
            "filename": out_filename,
            "download_url": f"/api/download/{out_filename}",
            "message": "PDF autollenado con IA exitosamente",
            "total_placed": -1
        }
    except Exception as e:
        print(f"[ERROR] ai_fill_pdf error: {e}")
        raise HTTPException(status_code=500, detail=f"Error en Autollenado IA: {str(e)}")

@app.get("/api/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/pdf"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
