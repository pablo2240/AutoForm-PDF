import os
import sys
import json
import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
env_file_path = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(env_file_path):
    load_dotenv(dotenv_path=env_file_path, override=True)
else:
    load_dotenv(override=True)

from backend.pdf_filling_agent.visual_processor import VisualPDFProcessor, VisualPlacement
from backend.db.session import get_db, SessionLocal
from backend.db.models import CommercialProfile
from backend.db.auth import hash_password, verify_password, create_session_token, verify_session_token, SESSION_MAX_AGE_SECONDS
from backend.auth_supabase import (
    get_current_user,
    require_admin,
    get_supabase_admin_client,
    get_supabase_user_client,
    decode_supabase_jwt
)

app = FastAPI(title="AutoForm PDF API")

cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    allow_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
else:
    allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
INPUT_DIR = os.path.join(PROJECT_ROOT, "input")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
SIGNATURES_DIR = os.path.join(DATA_DIR, "signatures")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SIGNATURES_DIR, exist_ok=True)

class SignaturePayload(BaseModel):
    image_base64: str
    filename: Optional[str] = "global_signature.png"
    position: Optional[Dict[str, float]] = None
    size: Optional[Dict[str, float]] = None

class CategorizedCompanyPayload(BaseModel):
    id: Optional[List[Dict[str, Any]]] = []
    contacto: Optional[List[Dict[str, Any]]] = []
    banco: Optional[List[Dict[str, Any]]] = []
    financiero: Optional[List[Dict[str, Any]]] = []
    otros: Optional[List[Dict[str, Any]]] = []

class EmployerProfilesPayload(BaseModel):
    profiles: Optional[List[Dict[str, Any]]] = []


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

class CommercialProfilePublicDTO(BaseModel):
    id: str
    profile_name: str
    nombre: str
    apellido: str
    cargo: str
    email: str
    celular: str
    role: Optional[str] = "commercial"
    is_active: bool

class CommercialProfileAdminDTO(BaseModel):
    id: str
    profile_name: str
    nombre: str
    apellido: str
    cargo: str
    email: str
    celular: str
    tipo_documento: Optional[str] = "C.C"
    documento_identidad: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_modified_by_ip: Optional[str] = None

class CommercialProfileCreateDTO(BaseModel):
    profile_name: str
    nombre: str
    apellido: str
    cargo: str
    email: str
    celular: str
    tipo_documento: Optional[str] = "C.C"
    documento_identidad: Optional[str] = None
    role: Optional[str] = "commercial"
    password: Optional[str] = None

class CommercialProfileUpdateDTO(BaseModel):
    profile_name: Optional[str] = None
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    cargo: Optional[str] = None
    email: Optional[str] = None
    celular: Optional[str] = None
    tipo_documento: Optional[str] = None
    documento_identidad: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class AdminLoginDTO(BaseModel):
    email: str
    password: str

class CommercialRegisterDTO(BaseModel):
    profile_name: Optional[str] = None
    nombre: str
    apellido: str
    cargo: str
    email: str
    celular: str
    tipo_documento: Optional[str] = "CC"
    documento_identidad: Optional[str] = None
    password: str

class TemplateMapping(BaseModel):
    template_id: str
    page_width: float
    page_height: float
    mappings: List[MappingItem]

class GenerateRequest(BaseModel):
    template_id: str
    template_version_id: Optional[str] = None
    mappings: Optional[List[MappingItem]] = None
    is_temporary: Optional[bool] = False
    commercial_profile_id: Optional[str] = None

class AiFillRequest(BaseModel):
    template_id: str
    template_version_id: Optional[str] = None
    commercial_profile_id: Optional[str] = None

class InviteUserDTO(BaseModel):
    email: str
    nombre: str
    apellido: str
    cargo: str
    celular: str
    tipo_documento: str = "C.C"
    documento_identidad: Optional[str] = None
    role: str = "commercial"

class StartFormFillDTO(BaseModel):
    template_version_id: str
    commercial_profile_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class CompleteFormFillDTO(BaseModel):
    history_id: str
    output_storage_path: str
    metadata: Optional[Dict[str, Any]] = None

class FailFormFillDTO(BaseModel):
    history_id: str
    error_message: str
    metadata: Optional[Dict[str, Any]] = None


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
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

@app.post("/api/company-data")
def update_company_data(data: Dict[str, Any]):
    path = os.path.join(DATA_DIR, "company_data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"status": "success", "message": "Company data saved successfully"}

@app.get("/api/signature")
def get_global_signature():
    sig_img_path = os.path.join(SIGNATURES_DIR, "global_signature.png")
    meta_path = os.path.join(SIGNATURES_DIR, "signature_metadata.json")
    if not os.path.exists(sig_img_path):
        return {"signature": None}
    
    metadata = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8-sig") as f:
                metadata = json.load(f)
        except Exception:
            pass

    import base64
    with open(sig_img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
        data_url = f"data:image/png;base64,{b64}"

    return {
        "signature": {
            "filename": metadata.get("filename", "global_signature.png"),
            "base64": data_url,
            "url": "/api/signature/image",
            "position": metadata.get("position", {"x": 0, "y": 0}),
            "size": metadata.get("size", {"width": 160, "height": 70})
        }
    }

@app.get("/api/signature/image")
def get_signature_image():
    sig_img_path = os.path.join(SIGNATURES_DIR, "global_signature.png")
    if not os.path.exists(sig_img_path):
        raise HTTPException(status_code=404, detail="No global signature found")
    return FileResponse(
        path=sig_img_path,
        media_type="image/png",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@app.post("/api/signature")
def save_global_signature(payload: SignaturePayload):
    import base64
    b64_str = payload.image_base64
    if "," in b64_str:
        b64_str = b64_str.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(b64_str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {str(e)}")

    sig_img_path = os.path.join(SIGNATURES_DIR, "global_signature.png")
    with open(sig_img_path, "wb") as f:
        f.write(img_bytes)

    meta = {
        "filename": payload.filename or "global_signature.png",
        "position": payload.position or {"x": 0, "y": 0},
        "size": payload.size or {"width": 160, "height": 70}
    }
    meta_path = os.path.join(SIGNATURES_DIR, "signature_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    comp_path = os.path.join(DATA_DIR, "company_data.json")
    if os.path.exists(comp_path):
        try:
            with open(comp_path, "r", encoding="utf-8-sig") as f:
                cd = json.load(f)
            cd["firma_global"] = "global_signature.png"
            with open(comp_path, "w", encoding="utf-8") as f:
                json.dump(cd, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARNING] Error updating firma_global in company_data.json: {e}")

    return {
        "status": "success",
        "message": "Global signature saved successfully",
        "signature": {
            "filename": meta["filename"],
            "url": "/api/signature/image",
            "position": meta["position"],
            "size": meta["size"]
        }
    }

@app.delete("/api/signature")
def delete_global_signature():
    sig_img_path = os.path.join(SIGNATURES_DIR, "global_signature.png")
    meta_path = os.path.join(SIGNATURES_DIR, "signature_metadata.json")
    if os.path.exists(sig_img_path):
        os.remove(sig_img_path)
    if os.path.exists(meta_path):
        os.remove(meta_path)

    comp_path = os.path.join(DATA_DIR, "company_data.json")
    if os.path.exists(comp_path):
        try:
            with open(comp_path, "r", encoding="utf-8-sig") as f:
                cd = json.load(f)
            if "firma_global" in cd:
                del cd["firma_global"]
                with open(comp_path, "w", encoding="utf-8") as f:
                    json.dump(cd, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    return {"status": "success", "message": "Global signature deleted successfully"}

@app.get("/api/categorized-company")
def get_categorized_company():
    """
    Retorna la estructura categorizada de datos de la empresa (ADR-0006, ADR-0007).
    Incluye categorías: id, contacto, banco, financiero y otros.
    """
    path = os.path.join(DATA_DIR, "categorized_company.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    comp_path = os.path.join(DATA_DIR, "company_data.json")
    comp_data = {}
    if os.path.exists(comp_path):
        with open(comp_path, "r", encoding="utf-8-sig") as f:
            comp_data = json.load(f)

    id_keys = ['nit', 'rut', 'razon_social', 'matricula', 'cedula', 'representante', 'tipo_documento', 'lugar_expedicion', 'ciudad', 'departamento', 'pais']
    contacto_keys = ['direccion', 'telefono', 'email', 'correo', 'celular', 'web', 'pagina']
    banco_keys = ['banco', 'cuenta', 'tipo_cuenta', 'titular']
    financiero_keys = ['activo', 'activos', 'pasivo', 'pasivos', 'patrimonio', 'ingreso', 'ingresos', 'egreso', 'egresos']

    default_cat = {
        "id": [],
        "contacto": [],
        "banco": [],
        "financiero": [],
        "otros": []
    }

    for key, val in comp_data.items():
        if key.startswith("kelly_") or key == "firma_global":
            continue
        val_str = str(val or "").strip()
        if not val_str:
            continue
        lower_key = key.lower()
        label = key.replace('_', ' ').title()

        category = 'otros'
        if any(k in lower_key for k in id_keys):
            category = 'id'
        elif any(k in lower_key for k in contacto_keys):
            category = 'contacto'
        elif any(k in lower_key for k in banco_keys):
            category = 'banco'
        elif any(k in lower_key for k in financiero_keys):
            category = 'financiero'

        default_cat[category].append({
            "id": f"cf-{key}",
            "key": key,
            "label": label,
            "value": val_str,
            "category": category
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(default_cat, f, indent=2, ensure_ascii=False)
    return default_cat

@app.post("/api/categorized-company")
def update_categorized_company(payload: Dict[str, Any]):
    path = os.path.join(DATA_DIR, "categorized_company.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return {"status": "success", "message": "Categorized company data saved successfully"}

@app.get("/api/employer-profiles")
def get_employer_profiles():
    path = os.path.join(DATA_DIR, "employer_profiles.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    comp_path = os.path.join(DATA_DIR, "company_data.json")
    comp_data = {}
    if os.path.exists(comp_path):
        with open(comp_path, "r", encoding="utf-8-sig") as f:
            comp_data = json.load(f)

    default_profiles = []
    if "kelly_delgado_nombre" in comp_data or "kelly_delgado_email" in comp_data:
        default_profiles.append({
            "id": "prof-kelly-delgado",
            "profileName": "Kelly Delgado",
            "nombre": comp_data.get("kelly_delgado_nombre", "Kelly Yohana"),
            "apellido": comp_data.get("kelly_delgado_apellido", "Delgado Macea"),
            "email": comp_data.get("kelly_delgado_email", "Kelly.Delgado@iaclatam.com"),
            "celular": comp_data.get("kelly_delgado_celular", "301 4750760"),
            "customFields": []
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(default_profiles, f, indent=2, ensure_ascii=False)
    return default_profiles

@app.post("/api/employer-profiles")
def update_employer_profiles(payload: List[Dict[str, Any]]):
    path = os.path.join(DATA_DIR, "employer_profiles.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return {"status": "success", "message": "Employer profiles saved successfully"}

# ---------------------------------------------------------------------------
# ADR-0008: Commercial Profiles & Administrative Security Endpoints
# ---------------------------------------------------------------------------

def resolve_commercial_profile(commercial_profile_id: Optional[str], token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Validates and resolves the commercial profile for PDF generation.
    Enforces conscious selection: requires either a valid active commercial profile ID or 'legal_rep_only'.
    Fails fast with HTTP 422 if omitted or empty.
    """
    if not commercial_profile_id or not str(commercial_profile_id).strip():
        raise HTTPException(
            status_code=422,
            detail="Se requiere seleccionar un responsable comercial o elegir 'legal_rep_only' antes de generar el PDF."
        )
    clean_id = str(commercial_profile_id).strip()
    if clean_id in ("legal_rep_only", "null", "None"):
        return None

    # Try resolving via Supabase if token provided
    if token:
        try:
            user_client = get_supabase_user_client(token)
            res = user_client.table("profiles").select("*").eq("id", clean_id).eq("is_active", True).single().execute()
            if res.data:
                profile = res.data
                return {
                    "id": str(profile.get("id")),
                    "profile_name": profile.get("display_name") or f"{profile.get('nombre', '')} {profile.get('apellido', '')}".strip(),
                    "nombre": profile.get("nombre", ""),
                    "apellido": profile.get("apellido", ""),
                    "cargo": profile.get("cargo", ""),
                    "email": profile.get("email", ""),
                    "celular": profile.get("celular", ""),
                    "tipo_documento": profile.get("tipo_documento", "C.C"),
                    "documento_identidad": profile.get("documento_identidad", ""),
                    "role": profile.get("role", "commercial"),
                    "is_active": profile.get("is_active", True)
                }
        except Exception:
            pass

    db = SessionLocal()
    try:
        cp = db.query(CommercialProfile).filter(
            CommercialProfile.id == clean_id,
            CommercialProfile.is_active == True
        ).first()
        if not cp:
            raise HTTPException(
                status_code=404,
                detail=f"El responsable comercial con ID '{clean_id}' no existe o está inactivo."
            )
        return cp.to_admin_dict()
    finally:
        db.close()

def get_current_admin_user(request: Request, db = Depends(get_db)):
    """Verifies HttpOnly cookie session or Authorization header for admin access."""
    token = request.cookies.get("admin_session")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(status_code=401, detail="Sesión administrativa no encontrada o credenciales requeridas.")

    payload = verify_session_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Sesión expirada o token inválido.")

    email = payload["email"]
    user = db.query(CommercialProfile).filter(
        CommercialProfile.email.ilike(email),
        CommercialProfile.is_active == True
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo.")
    return user

@app.get("/api/commercial-profiles")
def list_commercial_profiles_public(request: Request, db = Depends(get_db)):
    """
    Retorna catálogo público de perfiles comerciales activos.
    Si se presenta un token de Supabase, consulta la RPC get_company_commercial_profiles() respetando RLS.
    Si no, usa la lógica legacy SQLite.
    """
    token = request.cookies.get("admin_session")
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]

    if token:
        try:
            user_client = get_supabase_user_client(token)
            res = user_client.rpc("get_company_commercial_profiles").execute()
            if res.data is not None:
                return [
                    {
                        "id": str(r["id"]),
                        "profile_name": r.get("display_name") or f"{r.get('cargo', '')}",
                        "cargo": r.get("cargo", ""),
                        "email": r.get("email", ""),
                        "celular": r.get("celular", "")
                    }
                    for r in res.data
                ]
        except Exception:
            pass

    session_payload = verify_session_token(token) if token else None

    query = db.query(CommercialProfile).filter(CommercialProfile.is_active == True)
    if session_payload and session_payload.get("role") != "admin":
        user_email = session_payload.get("email", "").lower()
        rows = query.filter(CommercialProfile.email.ilike(user_email)).all()
    else:
        rows = query.all()

    return [CommercialProfilePublicDTO(**r.to_public_dict()) for r in rows]

# ==============================================================================
# Supabase Integration Endpoints (FastAPI)
# ==============================================================================

@app.get("/api/auth/me")
async def auth_me(user: Dict[str, Any] = Depends(get_current_user)):
    """Retorna los datos del perfil activo del usuario autenticado en Supabase."""
    return {
        "id": user["id"],
        "email": user["email"],
        "company_id": user["company_id"],
        "role": user["role"],
        "nombre": user["nombre"],
        "apellido": user["apellido"],
        "display_name": user["display_name"],
        "cargo": user["cargo"],
        "celular": user["celular"],
        "tipo_documento": user["tipo_documento"],
        "is_active": user["is_active"]
    }

@app.get("/api/company")
async def get_company_data(user: Dict[str, Any] = Depends(get_current_user)):
    """Retorna la información de la empresa correspondiente al usuario (vía RLS)."""
    try:
        res = user["user_client"].table("companies").select("*").eq("id", user["company_id"]).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
        return res.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al obtener empresa: {str(e)}")

@app.post("/api/admin/invite-user")
async def invite_user(dto: InviteUserDTO, admin: Dict[str, Any] = Depends(require_admin)):
    """
    Invita a un nuevo usuario corporativo utilizando Supabase Auth Admin.
    Asigna de forma infalsificable company_id y role en app_metadata.
    Genera un enlace seguro de activación/recuperación para que el usuario establezca su contraseña.
    """
    import re
    email_clean = dto.email.strip().lower()
    if not re.match(r"^[^@\s]+@(iaclatam\.com|iac\.com\.co)$", email_clean):
        raise HTTPException(
            status_code=400,
            detail="Dominio de correo no autorizado. Solo se permiten cuentas @iaclatam.com o @iac.com.co"
        )
    if dto.role not in ("admin", "commercial"):
        raise HTTPException(status_code=400, detail="Rol inválido. Se permite 'admin' o 'commercial'.")

    admin_client = get_supabase_admin_client()
    try:
        new_user_res = admin_client.auth.admin.create_user({
            "email": email_clean,
            "app_metadata": {
                "company_id": admin["company_id"],
                "role": dto.role
            },
            "user_metadata": {
                "nombre": dto.nombre.strip(),
                "apellido": dto.apellido.strip(),
                "cargo": dto.cargo.strip(),
                "celular": dto.celular.strip(),
                "tipo_documento": dto.tipo_documento,
                "documento_identidad": dto.documento_identidad.strip() if dto.documento_identidad else None
            },
            "email_confirm": True
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al crear usuario en Supabase Auth: {str(e)}")

    action_link = None
    try:
        link_res = admin_client.auth.admin.generate_link({
            "type": "recovery",
            "email": email_clean
        })
        if hasattr(link_res, "properties") and link_res.properties:
            action_link = getattr(link_res.properties, "action_link", None) or link_res.properties.get("action_link")
    except Exception as e:
        print(f"[WARNING] Could not generate activation recovery link: {e}")

    return {
        "status": "success",
        "user_id": new_user_res.user.id,
        "email": email_clean,
        "role": dto.role,
        "activation_link": action_link,
        "message": f"Usuario {email_clean} registrado con éxito."
    }

@app.post("/api/form-fill/start")
async def api_start_form_fill(dto: StartFormFillDTO, user: Dict[str, Any] = Depends(get_current_user)):
    """Inicia el autollenado de un formulario mediante la RPC start_form_fill en estado 'processing'."""
    try:
        res = user["user_client"].rpc("start_form_fill", {
            "p_template_version_id": dto.template_version_id,
            "p_commercial_profile_id": dto.commercial_profile_id,
            "p_metadata": dto.metadata
        }).execute()
        return {"history_id": res.data, "status": "processing"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al iniciar autollenado: {str(e)}")

@app.post("/api/form-fill/complete")
async def api_complete_form_fill(dto: CompleteFormFillDTO, user: Dict[str, Any] = Depends(get_current_user)):
    """Completa el ciclo de autollenado mediante la RPC complete_form_fill validando la ruta en Storage."""
    try:
        user["user_client"].rpc("complete_form_fill", {
            "p_history_id": dto.history_id,
            "p_output_storage_path": dto.output_storage_path,
            "p_metadata": dto.metadata
        }).execute()
        return {"status": "completed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al completar autollenado: {str(e)}")

@app.post("/api/form-fill/fail")
async def api_fail_form_fill(dto: FailFormFillDTO, user: Dict[str, Any] = Depends(get_current_user)):
    """Registra el fallo de un proceso de autollenado mediante la RPC fail_form_fill."""
    try:
        user["user_client"].rpc("fail_form_fill", {
            "p_history_id": dto.history_id,
            "p_error_message": dto.error_message,
            "p_metadata": dto.metadata
        }).execute()
        return {"status": "failed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al reportar fallo: {str(e)}")

@app.get("/api/form-fill/{history_id}/signed-url")
async def api_get_signed_url(history_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    """Genera una URL firmada de descarga temporal en Storage para el PDF generado."""
    try:
        hist_res = user["user_client"].table("form_fill_history").select("output_storage_path").eq("id", history_id).single().execute()
        if not hist_res.data or not hist_res.data.get("output_storage_path"):
            raise HTTPException(status_code=404, detail="Registro de llenado no encontrado o sin PDF generado.")
        path = hist_res.data["output_storage_path"]
        signed = user["user_client"].storage.from_("generated-pdfs").create_signed_url(path, expires_in=3600)
        url = signed.get("signedURL") or signed.get("signedUrl")
        return {"signed_url": url, "storage_path": path}
    except HTTPException:
        raise
    except Exception as e:
        if "PGRST116" in str(e) or "0 rows" in str(e):
            raise HTTPException(status_code=404, detail="Registro de llenado no encontrado o acceso denegado por RLS.")
        raise HTTPException(status_code=400, detail=f"Error al generar enlace firmado: {str(e)}")

@app.post("/api/admin/login")
@app.post("/api/auth/login")
def admin_login(dto: AdminLoginDTO, response: Response, db = Depends(get_db)):
    email_clean = dto.email.strip().lower()
    user = db.query(CommercialProfile).filter(
        CommercialProfile.email.ilike(email_clean),
        CommercialProfile.is_active == True
    ).first()

    if not user or not user.password_hash or not verify_password(dto.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas o usuario inactivo.")

    token = create_session_token(user.email, user.role)
    is_prod = os.getenv("ENVIRONMENT", "").lower() == "production"
    response.set_cookie(
        key="admin_session",
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=is_prod
    )
    return {
        "status": "success",
        "authenticated": True,
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "profile_name": user.profile_name,
        "nombre": user.nombre,
        "apellido": user.apellido,
        "cargo": user.cargo,
        "token": token
    }

@app.get("/api/auth/check-email")
def check_email_availability(email: str, db = Depends(get_db)):
    """Verifica si un correo electrónico ya está registrado en la base de datos."""
    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        return {"available": False, "exists": False, "message": "Formato de correo no válido"}
    existing = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(email_clean)).first()
    return {"available": existing is None, "exists": existing is not None}

@app.post("/api/auth/register")
def auth_register(dto: CommercialRegisterDTO, request: Request, response: Response, db = Depends(get_db)):
    """Registra un nuevo responsable comercial individual y abre su sesión de inmediato."""
    email_clean = dto.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="El correo electrónico ingresado no es válido.")

    # 1. Comprobar que no exista previamente en la base de datos
    existing = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(email_clean)).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"El correo electrónico '{email_clean}' ya se encuentra registrado. Por favor utiliza otro correo o inicia sesión."
        )

    # 2. Nombres y Apellidos: Validar longitud mínima de más de 3 caracteres en ambos campos
    nombre_clean = dto.nombre.strip()
    apellido_clean = dto.apellido.strip()
    if len(nombre_clean) <= 3:
        raise HTTPException(status_code=400, detail="El nombre debe tener más de 3 caracteres.")
    if len(apellido_clean) <= 3:
        raise HTTPException(status_code=400, detail="El apellido debe tener más de 3 caracteres.")

    # 3. Cargo: Validar longitud mínima de más de 4 caracteres
    cargo_clean = dto.cargo.strip()
    if len(cargo_clean) <= 4:
        raise HTTPException(status_code=400, detail="El cargo debe tener más de 4 caracteres.")

    # 4. Celular: Permitir únicamente números y exigir más de 9 dígitos
    celular_clean = dto.celular.strip()
    if not celular_clean.isdigit():
        raise HTTPException(status_code=400, detail="El número de celular debe contener únicamente números.")
    if len(celular_clean) <= 9:
        raise HTTPException(status_code=400, detail="El número de celular debe tener más de 9 dígitos.")

    # 5. Cédula: Permitir únicamente números y exigir más de 7 dígitos
    documento_clean = dto.documento_identidad.strip() if dto.documento_identidad else ""
    if not documento_clean:
        raise HTTPException(status_code=400, detail="El número de cédula es obligatorio.")
    if not documento_clean.isdigit():
        raise HTTPException(status_code=400, detail="El número de cédula debe contener únicamente números.")
    if len(documento_clean) <= 7:
        raise HTTPException(status_code=400, detail="El número de cédula debe tener más de 7 dígitos.")

    # 6. Contraseña
    if len(dto.password.strip()) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres.")

    client_ip = request.client.host if request.client else None
    pwd_hash = hash_password(dto.password.strip())

    display_name = dto.profile_name.strip() if (dto.profile_name and dto.profile_name.strip()) else f"{dto.nombre.strip()} {dto.apellido.strip()}"

    new_profile = CommercialProfile(
        profile_name=display_name,
        nombre=dto.nombre.strip(),
        apellido=dto.apellido.strip(),
        cargo=dto.cargo.strip() or "Comercial",
        email=email_clean,
        celular=dto.celular.strip(),
        tipo_documento=dto.tipo_documento or "CC",
        documento_identidad=dto.documento_identidad.strip() if dto.documento_identidad else None,
        role="commercial",
        password_hash=pwd_hash,
        is_active=True,
        last_modified_by_ip=client_ip
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)

    # Establish session immediately
    token = create_session_token(new_profile.email, new_profile.role)
    is_prod = os.getenv("ENVIRONMENT", "").lower() == "production"
    response.set_cookie(
        key="admin_session",
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=is_prod
    )
    return {
        "status": "success",
        "authenticated": True,
        "id": str(new_profile.id),
        "email": new_profile.email,
        "role": new_profile.role,
        "profile_name": new_profile.profile_name,
        "nombre": new_profile.nombre,
        "apellido": new_profile.apellido,
        "cargo": new_profile.cargo,
        "token": token
    }

@app.get("/api/admin/check")
@app.get("/api/auth/check")
def admin_check(request: Request, db = Depends(get_db)):
    try:
        user = get_current_admin_user(request, db)
        return {
            "authenticated": True,
            "id": str(user.id),
            "email": user.email,
            "role": user.role,
            "profile_name": user.profile_name,
            "nombre": user.nombre,
            "apellido": user.apellido,
            "cargo": user.cargo
        }
    except HTTPException:
        return {"authenticated": False}

@app.post("/api/admin/logout")
@app.post("/api/auth/logout")
def admin_logout(response: Response):
    response.delete_cookie("admin_session")
    return {"status": "success", "message": "Sesión cerrada"}

@app.get("/api/admin/commercial-profiles", response_model=List[CommercialProfileAdminDTO])
def list_commercial_profiles_admin(current_user: CommercialProfile = Depends(get_current_admin_user), db = Depends(get_db)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores tienen acceso a la gestión de responsables comerciales.")
    rows = db.query(CommercialProfile).order_by(CommercialProfile.created_at.desc()).all()
    return [CommercialProfileAdminDTO(**r.to_admin_dict()) for r in rows]

@app.post("/api/admin/commercial-profiles", response_model=CommercialProfileAdminDTO)
def create_commercial_profile(
    dto: CommercialProfileCreateDTO,
    request: Request,
    current_user: CommercialProfile = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden registrar nuevos perfiles comerciales.")

    existing = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(dto.email.strip())).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un perfil con el correo {dto.email}")

    client_ip = request.client.host if request.client else None
    pwd_hash = hash_password(dto.password) if dto.password else None
    new_profile = CommercialProfile(
        profile_name=dto.profile_name.strip(),
        nombre=dto.nombre.strip(),
        apellido=dto.apellido.strip(),
        cargo=dto.cargo.strip(),
        email=dto.email.strip().lower(),
        celular=dto.celular.strip(),
        tipo_documento=dto.tipo_documento or "C.C",
        documento_identidad=dto.documento_identidad.strip() if dto.documento_identidad else None,
        role=dto.role or "commercial",
        password_hash=pwd_hash,
        last_modified_by_ip=client_ip
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return CommercialProfileAdminDTO(**new_profile.to_admin_dict())

@app.put("/api/admin/commercial-profiles/{profile_id}", response_model=CommercialProfileAdminDTO)
def update_commercial_profile(
    profile_id: str,
    dto: CommercialProfileUpdateDTO,
    request: Request,
    current_user: CommercialProfile = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    profile = db.query(CommercialProfile).filter(CommercialProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado.")

    # Non-admins can only edit their own profile
    if current_user.role != "admin" and current_user.id != profile.id:
        raise HTTPException(status_code=403, detail="No tienes permisos para modificar otros perfiles.")

    if dto.profile_name is not None: profile.profile_name = dto.profile_name.strip()
    if dto.nombre is not None: profile.nombre = dto.nombre.strip()
    if dto.apellido is not None: profile.apellido = dto.apellido.strip()
    if dto.cargo is not None: profile.cargo = dto.cargo.strip()
    if dto.email is not None: profile.email = dto.email.strip().lower()
    if dto.celular is not None: profile.celular = dto.celular.strip()
    if dto.tipo_documento is not None: profile.tipo_documento = dto.tipo_documento
    if dto.documento_identidad is not None: profile.documento_identidad = dto.documento_identidad.strip()
    if dto.is_active is not None and current_user.role == "admin": profile.is_active = dto.is_active
    if dto.role is not None and current_user.role == "admin": profile.role = dto.role
    if dto.password: profile.password_hash = hash_password(dto.password)

    profile.last_modified_by_ip = request.client.host if request.client else None
    db.commit()
    db.refresh(profile)
    return CommercialProfileAdminDTO(**profile.to_admin_dict())

@app.delete("/api/admin/commercial-profiles/{profile_id}")
def delete_commercial_profile(
    profile_id: str,
    current_user: CommercialProfile = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden desactivar perfiles.")
    profile = db.query(CommercialProfile).filter(CommercialProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil no encontrado.")
    profile.is_active = False
    db.commit()
    return {"status": "success", "message": f"Perfil {profile.profile_name} desactivado."}


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
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

@app.post("/api/generate")
def generate_pdf(req: GenerateRequest, request: Request):
    # Check for Supabase Auth token
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    elif "admin_session" in request.cookies:
        token = request.cookies.get("admin_session")

    supabase_user = None
    if token:
        try:
            supabase_user = decode_supabase_jwt(token)
        except Exception:
            supabase_user = None

    # 0. Enforce conscious selection and resolve commercial profile (ADR-0008)
    resolved_cp = resolve_commercial_profile(req.commercial_profile_id, token=token)

    history_id = None
    user_client = None
    if supabase_user and req.template_version_id:
        try:
            user_client = get_supabase_user_client(token)
            comm_prof_id = None if req.commercial_profile_id in ("legal_rep_only", None, "null", "None") else req.commercial_profile_id
            start_res = user_client.rpc("start_form_fill", {
                "p_template_version_id": req.template_version_id,
                "p_commercial_profile_id": comm_prof_id,
                "p_metadata": {"is_temporary": req.is_temporary, "template_id": req.template_id}
            }).execute()
            history_id = start_res.data
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al iniciar ciclo de llenado en Supabase: {str(e)}")

    # 1. Load company data
    company_data_path = os.path.join(DATA_DIR, "company_data.json")
    if not os.path.exists(company_data_path):
        raise HTTPException(status_code=404, detail="Company data not found")
    with open(company_data_path, "r", encoding="utf-8-sig") as f:
        company_data = json.load(f)

    effective_data = dict(company_data)
    rep_full = company_data.get("representante_legal", "Guillermo Humberto Cañón Sarria")
    rep_correo = company_data.get("correo_rep", "guillermo.canon@iaclatam.com")
    rep_celular = company_data.get("celular_rep", "3104120217")
    rep_doc = company_data.get("numero_cedula", "98555384")

    # Default Contacto Principal (Representante Legal)
    effective_data["contacto_principal_nombre"] = rep_full
    effective_data["contacto_principal_correo"] = rep_correo
    effective_data["contacto_principal_celular"] = rep_celular
    effective_data["contacto_principal_cargo"] = "Representante Legal"
    effective_data["contacto_principal_documento"] = rep_doc

    if resolved_cp:
        cp_full = f"{resolved_cp.get('nombre', '')} {resolved_cp.get('apellido', '')}".strip() or resolved_cp.get("profile_name", "")
        effective_data["contacto_nombre"] = cp_full
        effective_data["contacto_correo"] = resolved_cp.get("email", "")
        effective_data["contacto_celular"] = resolved_cp.get("celular", "")
        effective_data["contacto_cargo"] = resolved_cp.get("cargo", "")
        effective_data["contacto_documento"] = resolved_cp.get("documento_identidad", "")
        effective_data["contacto_pagos_nombre"] = cp_full
        effective_data["contacto_pagos_correo"] = resolved_cp.get("email", "")
        effective_data["contacto_pagos_celular"] = resolved_cp.get("celular", "")
        effective_data["contacto_pagos_cargo"] = resolved_cp.get("cargo", "")
        effective_data["contacto_pagos_documento"] = resolved_cp.get("documento_identidad", "")
    else:
        effective_data["contacto_nombre"] = rep_full
        effective_data["contacto_correo"] = rep_correo
        effective_data["contacto_celular"] = rep_celular
        effective_data["contacto_cargo"] = "Representante Legal"
        effective_data["contacto_documento"] = rep_doc
        effective_data["contacto_pagos_nombre"] = rep_full
        effective_data["contacto_pagos_correo"] = rep_correo
        effective_data["contacto_pagos_celular"] = rep_celular
        effective_data["contacto_pagos_cargo"] = "Representante Legal"
        effective_data["contacto_pagos_documento"] = rep_doc

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

        if item_type == "image":
            img_b64 = style.get("image_base64")
            if not img_b64:
                sig_img_path = os.path.join(SIGNATURES_DIR, "global_signature.png")
                if os.path.exists(sig_img_path):
                    import base64
                    with open(sig_img_path, "rb") as f:
                        img_b64 = f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
            if img_b64:
                placements.append(
                    VisualPlacement(
                        page=item["page_number"],
                        rect=rect,
                        item_type="image",
                        image_base64=img_b64,
                        field_description=item.get("label", "Imagen / Firma")
                    )
                )
        else:
            custom_text = style.get("custom_text")
            if custom_text is not None and custom_text != "":
                value = custom_text
            else:
                value = effective_data.get(field_key, "")

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

    download_url = f"/api/download/{out_filename}"

    # Supabase Lifecycle & Storage Upload
    if history_id and user_client and supabase_user:
        company_id = supabase_user.get("app_metadata", {}).get("company_id")
        user_id = supabase_user.get("sub")
        storage_path = f"{company_id}/{user_id}/{history_id}.pdf"
        try:
            with open(out_path, "rb") as f:
                pdf_bytes = f.read()
            user_client.storage.from_("generated-pdfs").upload(
                storage_path,
                pdf_bytes,
                file_options={"content-type": "application/pdf"}
            )
            user_client.rpc("complete_form_fill", {
                "p_history_id": history_id,
                "p_output_storage_path": storage_path,
                "p_metadata": {"total_placed": len(placements)}
            }).execute()

            signed = user_client.storage.from_("generated-pdfs").create_signed_url(storage_path, expires_in=3600)
            download_url = signed.get("signedURL") or signed.get("signedUrl") or download_url
        except Exception as e:
            try:
                user_client.rpc("fail_form_fill", {
                    "p_history_id": history_id,
                    "p_error_message": str(e)
                }).execute()
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=f"Error en almacenamiento de Supabase: {str(e)}")

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
        "download_url": download_url,
        "total_placed": len(placements),
        "is_temporary": req.is_temporary,
        "history_id": history_id
    }

@app.post("/api/ai-fill")
def ai_fill_pdf(req: AiFillRequest, request: Request):
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    elif "admin_session" in request.cookies:
        token = request.cookies.get("admin_session")

    supabase_user = None
    if token:
        try:
            supabase_user = decode_supabase_jwt(token)
        except Exception:
            supabase_user = None

    # 0. Enforce conscious selection and resolve commercial profile (ADR-0008)
    resolved_cp = resolve_commercial_profile(req.commercial_profile_id, token=token)

    history_id = None
    user_client = None
    if supabase_user and req.template_version_id:
        try:
            user_client = get_supabase_user_client(token)
            comm_prof_id = None if req.commercial_profile_id in ("legal_rep_only", None, "null", "None") else req.commercial_profile_id
            start_res = user_client.rpc("start_form_fill", {
                "p_template_version_id": req.template_version_id,
                "p_commercial_profile_id": comm_prof_id,
                "p_metadata": {"mode": "ai-fill", "template_id": req.template_id}
            }).execute()
            history_id = start_res.data
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error al iniciar ciclo de llenado en Supabase: {str(e)}")

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
    with open(company_data_path, "r", encoding="utf-8-sig") as f:
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
        agent = PDFAgent(company_profile_path=company_data_path, commercial_profile=resolved_cp)
        output_path = agent.fill_pdf(pdf_path, instructions, output_dir=OUTPUT_DIR, mode="auto")
        out_filename = os.path.basename(output_path)
        download_url = f"/api/download/{out_filename}"

        if history_id and user_client and supabase_user:
            company_id = supabase_user.get("app_metadata", {}).get("company_id")
            user_id = supabase_user.get("sub")
            storage_path = f"{company_id}/{user_id}/{history_id}.pdf"
            with open(output_path, "rb") as f:
                pdf_bytes = f.read()
            user_client.storage.from_("generated-pdfs").upload(
                storage_path,
                pdf_bytes,
                file_options={"content-type": "application/pdf"}
            )
            user_client.rpc("complete_form_fill", {
                "p_history_id": history_id,
                "p_output_storage_path": storage_path,
                "p_metadata": {"total_placed": agent.last_audit_report.get("filled", -1) if agent.last_audit_report else -1}
            }).execute()
            signed = user_client.storage.from_("generated-pdfs").create_signed_url(storage_path, expires_in=3600)
            download_url = signed.get("signedURL") or signed.get("signedUrl") or download_url

        return {
            "status": "success",
            "filename": out_filename,
            "download_url": download_url,
            "message": "PDF autollenado con IA exitosamente",
            "total_placed": agent.last_audit_report.get("filled", -1) if agent.last_audit_report else -1,
            "audit_report": agent.last_audit_report,
            "history_id": history_id
        }
    except Exception as e:
        if history_id and user_client:
            try:
                user_client.rpc("fail_form_fill", {
                    "p_history_id": history_id,
                    "p_error_message": str(e)
                }).execute()
            except Exception:
                pass
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
