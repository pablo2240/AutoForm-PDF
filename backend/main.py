import os
import sys
import json
import shutil
import re
import time
import uuid
import secrets
import hashlib
import traceback
import unicodedata
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from sqlalchemy import func
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Response, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional, Tuple, Set

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
from backend.db.models import CommercialProfile, PasswordResetToken, UserDocument
from backend.db.auth import hash_password, verify_password, create_session_token, verify_session_token, SESSION_MAX_AGE_SECONDS
from backend.email_service import (
    send_password_reset_email,
    get_email_provider,
    get_smtp_config,
    get_missing_smtp_vars,
    get_graph_config,
    get_missing_graph_vars,
    mask_email,
    sanitize_safe_log
)
from backend.auth_supabase import (
    get_current_user,
    require_admin,
    get_supabase_admin_client,
    get_supabase_user_client,
    decode_supabase_jwt
)

app = FastAPI(title="AutoForm PDF API")

from backend.reference_api import router as reference_library_router
app.include_router(reference_library_router)

def resolve_cors_origins(app_env: Optional[str] = None, raw_origins: Optional[str] = None) -> list[str]:
    """
    Resolves and enforces CORS origins based on the execution environment.

    Rules:
    - In staging and production environments, CORS_ORIGINS must be explicitly defined
      and non-empty. Fallbacks are strictly prohibited.
    - In production, origins containing 'localhost' or '127.0.0.1' are rejected, and at least
      one valid production origin must be present.
    - In local/development/test environments, if CORS_ORIGINS is not set, a safe set of
      local development origins is used.
    """
    env = (app_env if app_env is not None else os.getenv("APP_ENVIRONMENT", os.getenv("ENVIRONMENT", "local"))).lower()
    origins_str = raw_origins if raw_origins is not None else os.getenv("CORS_ORIGINS", "")

    if env in ("production", "staging"):
        if not origins_str or not origins_str.strip():
            raise RuntimeError(
                f"CORS_ORIGINS environment variable is required and must be explicitly defined in {env} environment."
            )
        parsed = [o.strip() for o in origins_str.split(",") if o.strip()]
        if not parsed:
            raise RuntimeError(
                f"CORS_ORIGINS environment variable cannot be empty in {env} environment."
            )
        if env == "production":
            if any(o == "*" for o in parsed):
                raise RuntimeError(
                    "CORS_ORIGINS wildcard '*' is strictly forbidden in production environment."
                )
            prod_origins = [o for o in parsed if not ("localhost" in o or "127.0.0.1" in o)]
            if not prod_origins:
                raise RuntimeError(
                    "CORS_ORIGINS must contain at least one valid non-localhost origin in production environment."
                )
            return prod_origins
        return parsed
    else:
        if origins_str and origins_str.strip():
            return [o.strip() for o in origins_str.split(",") if o.strip()]
        return [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000"
        ]

APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", os.getenv("ENVIRONMENT", "local")).lower()
cors_origins_env = os.getenv("CORS_ORIGINS", "")
allow_origins = resolve_cors_origins(APP_ENVIRONMENT, cors_origins_env)

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

ACTIVE_SLOT_FILE = os.path.join(DATA_DIR, "active_slot.json")

def get_active_slot() -> Optional[dict]:
    """Fail-closed: All access to legacy active_slot.json is forbidden under ADR-0011."""
    raise RuntimeError("Deprecated legacy active_slot.json access. Use user_documents under auth context (ADR-0011 fail-closed).")

def set_active_slot(template_id: str, filename: str):
    """Fail-closed: All writes to legacy active_slot.json are forbidden under ADR-0011."""
    raise RuntimeError("Deprecated legacy active_slot.json write. Use user_documents under auth context (ADR-0011 fail-closed).")

def clear_active_slot():
    """Fail-closed: All clearing of legacy active_slot.json is forbidden under ADR-0011."""
    raise RuntimeError("Deprecated legacy active_slot.json clear. Use user_documents under auth context (ADR-0011 fail-closed).")

def parse_storage_path(storage_path: str) -> Tuple[str, str]:
    """
    Descompone una ruta canónica de Storage en tupla (bucket, key).
    Formatos soportados:
    - 'templates/company_id/user_id/file.pdf' -> ('templates', 'company_id/user_id/file.pdf')
    - 'generated-pdfs/company_id/user_id/file.pdf' -> ('generated-pdfs', 'company_id/user_id/file.pdf')
    - 'company_id/user_id/file.pdf' -> ('templates', 'company_id/user_id/file.pdf')
    """
    if not storage_path:
        return ("templates", "")
    for known_bucket in ("templates", "generated-pdfs", "signatures"):
        if storage_path.startswith(f"{known_bucket}/"):
            return (known_bucket, storage_path[len(known_bucket) + 1:])
    return ("templates", storage_path)

def get_user_pdf_bytes(user_id: str, doc_row: Dict[str, Any]) -> bytes:
    """
    Obtiene los bytes del PDF para el usuario autenticado:
    1. Revisa caché efímera local en input/{user_id}/{filename}
    2. Si no existe o está corrupta, descarga bajo demanda desde Supabase Storage
    3. Almacena en caché efímera local input/{user_id}/{filename}
    4. Retorna bytes
    """
    doc_id = doc_row.get("id")
    filename = doc_row.get("filename")
    storage_path = doc_row.get("storage_path")

    candidates = []
    if doc_id:
        candidates.append(os.path.join(INPUT_DIR, str(user_id), f"{doc_id}.pdf"))
    if filename:
        candidates.append(os.path.join(INPUT_DIR, str(user_id), filename))

    for user_cache_path in candidates:
        if os.path.exists(user_cache_path):
            try:
                with open(user_cache_path, "rb") as f:
                    content = f.read()
                if content:
                    return content
            except Exception as e:
                print(f"[WARN] Error reading local user cache {user_cache_path}: {e}")

    # Descarga autoritativa desde Supabase Storage
    if storage_path:
        bucket, key = parse_storage_path(storage_path)
        try:
            admin_client = get_supabase_admin_client()
            content = admin_client.storage.from_(bucket).download(key)
            if content:
                for user_cache_path in candidates:
                    try:
                        os.makedirs(os.path.dirname(user_cache_path), exist_ok=True)
                        with open(user_cache_path, "wb") as f:
                            f.write(content)
                    except Exception as e:
                        print(f"[WARN] Error updating local user cache {user_cache_path}: {e}")
                return content
        except Exception as e:
            print(f"[WARN] Error downloading from Supabase Storage {bucket}/{key}: {e}")

    raise HTTPException(
        status_code=404,
        detail="No se encontró el contenido del documento en almacenamiento ni en caché."
    )

def resolve_user_document(
    user_id: str,
    template_identifier: str,
    is_admin: bool = False,
    company_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Busca de manera autoritativa un documento en user_documents por id (UUID) o template_code,
    garantizando aislamiento estricto por usuario autenticado.
    Si el documento pertenece a otro usuario o no se encuentra con un UUID válido,
    devuelve HTTP 403 Forbidden para impedir enumeración ciega.
    """
    admin_client = None
    try:
        admin_client = get_supabase_admin_client()
    except Exception:
        pass

    is_valid_uuid = False
    try:
        uuid.UUID(str(template_identifier))
        is_valid_uuid = True
    except Exception:
        pass

    # 1. Supabase (Authoritative)
    if admin_client:
        try:
            if is_valid_uuid:
                res = admin_client.table("user_documents").select("*").eq("id", template_identifier).limit(1).execute()
                if res.data and len(res.data) > 0:
                    found_doc = res.data[0]
                    if str(found_doc.get("user_id")) == str(user_id):
                        return found_doc
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Acceso denegado: no tienes permisos para acceder a este documento."
                        )
            else:
                # Búsqueda por template_code para el usuario autenticado
                res_code = (
                    admin_client.table("user_documents")
                    .select("*")
                    .eq("user_id", user_id)
                    .eq("template_code", template_identifier)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if res_code.data and len(res_code.data) > 0:
                    return res_code.data[0]

                # Verificar si pertenece a otro usuario para denegar explícitamente con 403
                res_other = (
                    admin_client.table("user_documents")
                    .select("id")
                    .eq("template_code", template_identifier)
                    .limit(1)
                    .execute()
                )
                if res_other.data and len(res_other.data) > 0:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Acceso denegado: no tienes permisos para acceder a este documento."
                    )
        except HTTPException:
            raise
        except Exception as e:
            print(f"[WARN] Error resolving user document in Supabase: {e}")

    # 2. Fallback SQLite local (entorno dev/test)
    if APP_ENVIRONMENT != "production":
        db = SessionLocal()
        try:
            if is_valid_uuid:
                local_doc = db.query(UserDocument).filter(UserDocument.id == template_identifier).first()
                if local_doc:
                    if str(local_doc.user_id) == str(user_id):
                        return local_doc.to_dict()
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Acceso denegado: no tienes permisos para acceder a este documento."
                        )
            else:
                local_doc = (
                    db.query(UserDocument)
                    .filter(UserDocument.user_id == user_id, UserDocument.template_code == template_identifier)
                    .order_by(UserDocument.created_at.desc())
                    .first()
                )
                if local_doc:
                    return local_doc.to_dict()

                # Verificar si pertenece a otro usuario en SQLite
                other_doc = db.query(UserDocument).filter(UserDocument.template_code == template_identifier).first()
                if other_doc:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Acceso denegado: no tienes permisos para acceder a este documento."
                    )
        finally:
            db.close()

    # 3. No encontrado
    if is_valid_uuid:
        # Anti-enumeración para UUIDs no encontrados
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado o documento no autorizado."
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Documento '{template_identifier}' no encontrado."
    )

def resolve_user_pdf_path(
    user_id: str,
    template_identifier: str,
    is_admin: bool = False,
    company_id: Optional[str] = None
) -> str:
    """
    Retorna la ruta al archivo PDF en la caché local del usuario.
    Si el archivo no está en caché (por ejemplo tras reinicio de contenedor en Render),
    lo descarga bajo demanda desde Supabase Storage.
    """
    doc = resolve_user_document(user_id, template_identifier, is_admin=is_admin, company_id=company_id)
    filename = doc["filename"]
    user_cache_path = os.path.join(INPUT_DIR, str(user_id), filename)

    if not os.path.exists(user_cache_path) or os.path.getsize(user_cache_path) == 0:
        pdf_bytes = get_user_pdf_bytes(user_id, doc)
        os.makedirs(os.path.dirname(user_cache_path), exist_ok=True)
        with open(user_cache_path, "wb") as f:
            f.write(pdf_bytes)

    return user_cache_path

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
    ciudad: Optional[str] = ""
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
    ciudad: Optional[str] = ""
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
    ciudad: Optional[str] = None
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
    ciudad: Optional[str] = None
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
    ciudad: str
    tipo_documento: Optional[str] = "CC"
    documento_identidad: str
    password: str

class ForgotPasswordRequestDTO(BaseModel):
    email: str

class VerifyResetTokenResponseDTO(BaseModel):
    valid: bool
    masked_email: Optional[str] = None
    message: Optional[str] = None

class ResetPasswordRequestDTO(BaseModel):
    token: str
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

def sync_company_data_to_supabase(data: Dict[str, Any]):
    """Sincroniza cambios en datos corporativos con las tablas de Supabase (companies, legal_representatives, company_bank_accounts)."""
    try:
        admin_client = get_supabase_admin_client()
        if not admin_client:
            return
        company_id = os.getenv("DEFAULT_COMPANY_ID")
        if not company_id:
            try:
                c_res = admin_client.table("companies").select("id").eq("is_active", True).limit(1).execute()
                if c_res.data and len(c_res.data) > 0:
                    company_id = c_res.data[0]["id"]
            except Exception:
                pass
        if not company_id:
            company_id = "8cb5378d-b9a7-4e2e-aa36-2718371731a6"

        comp_update = {}
        if "razon_social" in data:
            comp_update["razon_social"] = str(data["razon_social"] or "")
        if "nit" in data:
            nit_val = str(data["nit"] or "").strip()
            if nit_val:
                nit_raw = nit_val.replace("-", "").strip()
                if len(nit_raw) == 10 and not data.get("dv"):
                    comp_update["nit"] = nit_raw[:9]
                    comp_update["dv"] = nit_raw[9:]
                else:
                    comp_update["nit"] = nit_val.split("-")[0].strip()
            else:
                comp_update["nit"] = ""
        if "dv" in data:
            comp_update["dv"] = str(data["dv"] or "").strip()
        if "ciudad" in data:
            comp_update["ciudad"] = str(data["ciudad"] or "")
        if "departamento" in data:
            comp_update["departamento"] = str(data["departamento"] or "")
        if "pais" in data:
            comp_update["pais"] = str(data["pais"] or "")
        if "direccion_principal" in data:
            comp_update["direccion_principal"] = str(data["direccion_principal"] or "")
        if "telefono" in data:
            comp_update["telefono"] = str(data["telefono"] or "")
        if "pagina_web" in data:
            comp_update["pagina_web"] = str(data["pagina_web"] or "")

        for num_f in ["total_activos", "total_pasivos", "total_patrimonio", "total_ingresos_mensuales", "total_egresos_mensuales"]:
            if num_f in data:
                val = data[num_f]
                if val is not None and str(val).strip() != "":
                    try:
                        comp_update[num_f] = float(str(val).replace(",", "").replace("$", "").strip())
                    except Exception:
                        pass
                else:
                    comp_update[num_f] = None

        if comp_update:
            try:
                admin_client.table("companies").update(comp_update).eq("id", company_id).execute()
            except Exception as e_comp:
                print(f"[WARN] Error actualizando tabla companies en Supabase: {e_comp}")

        leg_update = {}
        if "representante_legal" in data:
            leg_update["nombre_completo"] = str(data["representante_legal"] or "")
        if "representante_nombre" in data:
            leg_update["nombres"] = str(data["representante_nombre"] or "")
        if "representante_apellido" in data:
            leg_update["apellidos"] = str(data["representante_apellido"] or "")
        if "tipo_documento" in data:
            leg_update["tipo_documento"] = str(data["tipo_documento"] or "")
        if "numero_cedula" in data:
            leg_update["numero_documento"] = str(data["numero_cedula"] or "")
        if "lugar_expedicion_rep" in data:
            leg_update["lugar_expedicion"] = str(data["lugar_expedicion_rep"] or "")
        if "correo_rep" in data:
            leg_update["email"] = str(data["correo_rep"] or "")
        if "celular_rep" in data:
            leg_update["celular"] = str(data["celular_rep"] or "")

        if leg_update:
            try:
                admin_client.table("legal_representatives").update(leg_update).eq("company_id", company_id).eq("es_principal", True).execute()
            except Exception as e_leg:
                print(f"[WARN] Error actualizando legal_representatives en Supabase: {e_leg}")

        bank_update = {}
        if "entidad_bancaria" in data:
            bank_update["entidad_bancaria"] = str(data["entidad_bancaria"] or "")
        if "tipo_cuenta" in data:
            bank_update["tipo_cuenta"] = str(data["tipo_cuenta"] or "")
        if "numero_cuenta" in data:
            bank_update["numero_cuenta"] = str(data["numero_cuenta"] or "")

        if bank_update:
            try:
                admin_client.table("company_bank_accounts").update(bank_update).eq("company_id", company_id).eq("es_principal", True).execute()
            except Exception as e_bank:
                print(f"[WARN] Error actualizando company_bank_accounts en Supabase: {e_bank}")
    except Exception as e:
        print(f"[WARN] Fallo general sincronizando empresa con Supabase: {e}")

@app.get("/api/company-data")
def get_company_data():
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
        "tipo_cuenta": "Ahorros",
        "total_activos": "16151175009",
        "total_pasivos": "8831977528",
        "total_patrimonio": "7319197482",
        "total_ingresos_mensuales": "1110748257",
        "total_egresos_mensuales": "975086377"
    }
    path = os.path.join(DATA_DIR, "company_data.json")
    saved_data = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                content = json.load(f)
                if isinstance(content, dict):
                    saved_data = content
        except Exception:
            pass

    merged = {**default_data, **saved_data}

    # Enriquecer autoritativamente desde Supabase si está disponible
    try:
        admin_client = get_supabase_admin_client()
        if admin_client:
            company_id = os.getenv("DEFAULT_COMPANY_ID")
            if not company_id:
                try:
                    c_res = admin_client.table("companies").select("id").eq("is_active", True).limit(1).execute()
                    if c_res.data and len(c_res.data) > 0:
                        company_id = c_res.data[0]["id"]
                except Exception:
                    pass
            if not company_id:
                company_id = "8cb5378d-b9a7-4e2e-aa36-2718371731a6"

            comp_res = admin_client.table("companies").select("*").eq("id", company_id).single().execute()
            if comp_res.data:
                c = comp_res.data
                if c.get("razon_social") and saved_data.get("razon_social") != "": merged["razon_social"] = c["razon_social"]
                if c.get("nit") and saved_data.get("nit") != "":
                    nit_val = str(c["nit"])
                    dv_val = str(c.get("dv") or "")
                    merged["nit"] = f"{nit_val}{dv_val}" if dv_val else nit_val
                if c.get("ciudad") and saved_data.get("ciudad") != "": merged["ciudad"] = c["ciudad"]
                if c.get("departamento") and saved_data.get("departamento") != "": merged["departamento"] = c["departamento"]
                if c.get("pais") and saved_data.get("pais") != "": merged["pais"] = c["pais"]
                if c.get("direccion_principal") and saved_data.get("direccion_principal") != "": merged["direccion_principal"] = c["direccion_principal"]
                if c.get("telefono") and saved_data.get("telefono") != "": merged["telefono"] = str(c["telefono"])
                if c.get("pagina_web") and saved_data.get("pagina_web") != "": merged["pagina_web"] = c["pagina_web"]
                for num_k in ["total_activos", "total_pasivos", "total_patrimonio", "total_ingresos_mensuales", "total_egresos_mensuales"]:
                    if c.get(num_k) is not None and saved_data.get(num_k) != "":
                        merged[num_k] = str(int(c[num_k]))

            leg_res = admin_client.table("legal_representatives").select("*").eq("company_id", company_id).eq("es_principal", True).execute()
            if leg_res.data and len(leg_res.data) > 0:
                l = leg_res.data[0]
                if l.get("nombre_completo") and saved_data.get("representante_legal") != "": merged["representante_legal"] = l["nombre_completo"]
                if l.get("nombres") and saved_data.get("representante_nombre") != "": merged["representante_nombre"] = l["nombres"]
                if l.get("apellidos") and saved_data.get("representante_apellido") != "": merged["representante_apellido"] = l["apellidos"]
                if l.get("tipo_documento") and saved_data.get("tipo_documento") != "": merged["tipo_documento"] = l["tipo_documento"]
                if l.get("numero_cedula") and saved_data.get("numero_cedula") != "": merged["numero_cedula"] = str(l["numero_documento"])
                if l.get("lugar_expedicion") and saved_data.get("lugar_expedicion_rep") != "": merged["lugar_expedicion_rep"] = l["lugar_expedicion"]
                if l.get("fecha_expedicion") and saved_data.get("fecha_expedicion_rep") != "": merged["fecha_expedicion_rep"] = str(l["fecha_expedicion"])
                if l.get("email") and saved_data.get("correo_rep") != "": merged["correo_rep"] = l["email"]
                if l.get("celular") and saved_data.get("celular_rep") != "": merged["celular_rep"] = str(l["celular"])

            bank_res = admin_client.table("company_bank_accounts").select("*").eq("company_id", company_id).eq("es_principal", True).execute()
            if bank_res.data and len(bank_res.data) > 0:
                b = bank_res.data[0]
                if b.get("entidad_bancaria") and saved_data.get("entidad_bancaria") != "": merged["entidad_bancaria"] = b["entidad_bancaria"]
                if b.get("tipo_cuenta") and saved_data.get("tipo_cuenta") != "": merged["tipo_cuenta"] = b["tipo_cuenta"]
                if b.get("numero_cuenta") and saved_data.get("numero_cuenta") != "": merged["numero_cuenta"] = str(b["numero_cuenta"])
    except Exception as e_load_supa:
        print(f"[WARN] Error cargando datos corporativos desde Supabase: {e_load_supa}")

    # Preservar explícitamente cualquier clave que el usuario haya dejado en blanco en saved_data
    for k, v in saved_data.items():
        if v == "":
            merged[k] = ""

    # Guardar en cache local para acceso sin conexión
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return merged

@app.post("/api/company-data")
def update_company_data(data: Dict[str, Any]):
    path = os.path.join(DATA_DIR, "company_data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    sync_company_data_to_supabase(data)
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
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass

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

def sync_profile_to_supabase_and_local(
    profile_data: Dict[str, Any],
    db: Optional[Any] = None,
    client_ip: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sincroniza un perfil de empleador/comercial tanto en Supabase (Auth + public.profiles)
    como en la base de datos local relacional SQLite (CommercialProfile).
    Garantiza persistencia definitiva con campo cargo entre reinicios y cambios de entorno.
    """
    email = str(profile_data.get("email") or "").strip().lower()
    nombre = str(profile_data.get("nombre") or "").strip()
    apellido = str(profile_data.get("apellido") or "").strip()
    cargo = str(profile_data.get("cargo") or "").strip()
    celular = str(profile_data.get("celular") or "").strip()
    profile_name = str(
        profile_data.get("profileName")
        or profile_data.get("profile_name")
        or f"{nombre} {apellido}".strip()
    ).strip()
    ciudad = str(profile_data.get("ciudad") or "").strip()
    tipo_documento = str(profile_data.get("tipo_documento") or "C.C").strip()
    documento_identidad = profile_data.get("documento_identidad")
    if documento_identidad:
        documento_identidad = str(documento_identidad).strip()
    role = str(profile_data.get("role") or "commercial").strip()
    raw_id = profile_data.get("id")
    profile_id = str(raw_id).strip() if raw_id else None
    password = profile_data.get("password")

    if not profile_name:
        profile_name = f"{nombre} {apellido}".strip() or email or "Usuario"

    if not cargo:
        cargo = "Asesor Comercial"

    auth_user_id = None
    close_db_here = False
    if db is None:
        try:
            db = SessionLocal()
            close_db_here = True
        except Exception:
            db = None

    # 1. Sincronización en Supabase
    try:
        admin_client = get_supabase_admin_client()
        if admin_client:
            resolved_company_id = os.getenv("DEFAULT_COMPANY_ID")
            if not resolved_company_id:
                try:
                    c_res = admin_client.table("companies").select("id").eq("is_active", True).limit(1).execute()
                    if c_res.data and len(c_res.data) > 0:
                        resolved_company_id = c_res.data[0]["id"]
                except Exception:
                    pass
            if not resolved_company_id:
                resolved_company_id = "8cb5378d-b9a7-4e2e-aa36-2718371731a6"

            # Buscar usuario existente en Supabase Auth por email o ID
            if email:
                try:
                    all_users = admin_client.auth.admin.list_users(page=1, per_page=1000)
                    for u in all_users:
                        if (u.email or "").lower() == email:
                            auth_user_id = str(u.id)
                            break
                except Exception as e_list:
                    print(f"[WARN] Error listando usuarios en Supabase Auth: {e_list}")

            if not auth_user_id and profile_id and len(profile_id) == 36:
                try:
                    u_res = admin_client.auth.admin.get_user_by_id(profile_id)
                    u_obj = getattr(u_res, "user", None) or u_res
                    if u_obj:
                        auth_user_id = str(getattr(u_obj, "id", None) or (u_obj.get("id") if isinstance(u_obj, dict) else None))
                except Exception:
                    pass

            # Si no existe en Supabase Auth y tiene email corporativo válido, crearlo
            if not auth_user_id and email and ("@iaclatam.com" in email or "@iac.com.co" in email):
                temp_pwd = password or f"SmartForm{secrets.token_hex(4)}!"
                auth_payload = {
                    "email": email,
                    "password": temp_pwd,
                    "email_confirm": True,
                    "app_metadata": {
                        "company_id": resolved_company_id,
                        "role": role if role in ("admin", "commercial") else "commercial",
                        "cargo": cargo,
                        "tipo_documento": tipo_documento
                    },
                    "user_metadata": {
                        "nombre": nombre,
                        "apellido": apellido,
                        "cargo": cargo,
                        "celular": celular,
                        "ciudad": ciudad,
                        "tipo_documento": tipo_documento,
                        "documento_identidad": documento_identidad
                    }
                }
                try:
                    new_user_res = admin_client.auth.admin.create_user(auth_payload)
                    u_created = getattr(new_user_res, "user", None) or new_user_res
                    auth_user_id = str(getattr(u_created, "id", None) or (u_created.get("id") if isinstance(u_created, dict) else None))
                except Exception as e_create:
                    print(f"[WARN] No se pudo crear usuario en Supabase Auth para {email}: {e_create}")

            # Upsert o update directo en public.profiles
            supa_uid = auth_user_id or (profile_id if (profile_id and len(profile_id) == 36) else None)
            if supa_uid:
                prof_record = {
                    "id": supa_uid,
                    "company_id": resolved_company_id,
                    "email": email,
                    "nombre": nombre,
                    "apellido": apellido,
                    "display_name": profile_name,
                    "cargo": cargo,
                    "celular": celular,
                    "tipo_documento": tipo_documento,
                    "role": role if role in ("admin", "commercial") else "commercial",
                    "is_active": True
                }
                if ciudad:
                    prof_record["ciudad"] = ciudad
                if documento_identidad:
                    prof_record["documento_identidad"] = documento_identidad
                try:
                    admin_client.table("profiles").upsert(prof_record).execute()
                except Exception as e_upsert:
                    print(f"[WARN] Error en upsert de public.profiles en Supabase: {e_upsert}")
            elif email:
                try:
                    admin_client.table("profiles").update({
                        "cargo": cargo,
                        "display_name": profile_name,
                        "nombre": nombre,
                        "apellido": apellido,
                        "celular": celular
                    }).eq("email", email).execute()
                except Exception:
                    pass
    except Exception as e_supa_general:
        print(f"[WARN] Error general sincronizando perfil con Supabase: {e_supa_general}")

    # 2. Sincronización en SQLite (CommercialProfile)
    final_id = auth_user_id or profile_id or str(uuid.uuid4())
    if db is not None:
        try:
            existing_cp = None
            if email:
                existing_cp = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(email)).first()
            if not existing_cp and final_id:
                existing_cp = db.query(CommercialProfile).filter(CommercialProfile.id == final_id).first()

            if existing_cp:
                existing_cp.profile_name = profile_name
                if nombre: existing_cp.nombre = nombre
                if apellido: existing_cp.apellido = apellido
                if cargo: existing_cp.cargo = cargo
                if celular: existing_cp.celular = celular
                if ciudad: existing_cp.ciudad = ciudad
                if tipo_documento: existing_cp.tipo_documento = tipo_documento
                if documento_identidad: existing_cp.documento_identidad = documento_identidad
                existing_cp.is_active = True
                if client_ip: existing_cp.last_modified_by_ip = client_ip
                final_id = existing_cp.id
            else:
                new_cp = CommercialProfile(
                    id=final_id,
                    profile_name=profile_name,
                    nombre=nombre or profile_name,
                    apellido=apellido or "",
                    cargo=cargo,
                    email=email,
                    celular=celular or "3000000000",
                    ciudad=ciudad or None,
                    tipo_documento=tipo_documento or "C.C",
                    documento_identidad=documento_identidad,
                    role=role if role in ("admin", "commercial") else "commercial",
                    is_active=True,
                    last_modified_by_ip=client_ip
                )
                db.add(new_cp)
                final_id = new_cp.id
            db.commit()
        except Exception as e_db:
            db.rollback()
            print(f"[WARN] Error guardando perfil en SQLite: {e_db}")
        finally:
            if close_db_here:
                db.close()

    return {
        "id": final_id,
        "profileName": profile_name,
        "nombre": nombre,
        "apellido": apellido,
        "cargo": cargo,
        "email": email,
        "celular": celular,
        "customFields": profile_data.get("customFields") or []
    }

@app.get("/api/employer-profiles")
def get_employer_profiles(db = Depends(get_db)):
    path = os.path.join(DATA_DIR, "employer_profiles.json")
    profiles_dict: Dict[str, Dict[str, Any]] = {}

    # 1. Leer archivo local si existe
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                saved = json.load(f)
                if isinstance(saved, list):
                    for p in saved:
                        key = (p.get("email") or p.get("id") or "").strip().lower()
                        if key:
                            profiles_dict[key] = p
        except Exception as e:
            print(f"[WARN] Error leyendo employer_profiles.json: {e}")

    # 2. Sincronizar desde Supabase public.profiles (persistencia autoritativa en la nube)
    try:
        admin_client = get_supabase_admin_client()
        if admin_client:
            res = admin_client.table("profiles").select("*").eq("is_active", True).execute()
            if res.data:
                for row in res.data:
                    email_key = (row.get("email") or str(row.get("id", ""))).strip().lower()
                    if not email_key:
                        continue
                    disp_name = row.get("display_name") or f"{row.get('nombre', '')} {row.get('apellido', '')}".strip()
                    cargo_val = row.get("cargo") or ""
                    if email_key in profiles_dict:
                        existing = profiles_dict[email_key]
                        if not existing.get("cargo") and cargo_val:
                            existing["cargo"] = cargo_val
                        if not existing.get("nombre") and row.get("nombre"):
                            existing["nombre"] = row.get("nombre")
                        if not existing.get("apellido") and row.get("apellido"):
                            existing["apellido"] = row.get("apellido")
                        if not existing.get("celular") and row.get("celular"):
                            existing["celular"] = row.get("celular")
                        existing["id"] = str(row["id"])
                        if not existing.get("profileName"):
                            existing["profileName"] = disp_name
                    else:
                        profiles_dict[email_key] = {
                            "id": str(row["id"]),
                            "profileName": disp_name,
                            "nombre": row.get("nombre") or "",
                            "apellido": row.get("apellido") or "",
                            "cargo": cargo_val,
                            "email": row.get("email") or "",
                            "celular": row.get("celular") or "",
                            "customFields": []
                        }
    except Exception as e_supa:
        print(f"[WARN] Error cargando perfiles desde Supabase: {e_supa}")

    # 3. Sincronizar desde SQLite CommercialProfile
    close_db_local = False
    active_db = db
    if active_db is None:
        try:
            active_db = SessionLocal()
            close_db_local = True
        except Exception:
            active_db = None

    if active_db is not None:
        try:
            sqlite_profiles = active_db.query(CommercialProfile).filter(CommercialProfile.is_active == True).all()
            for sp in sqlite_profiles:
                email_key = (sp.email or sp.id or "").strip().lower()
                if not email_key:
                    continue
                if email_key in profiles_dict:
                    existing = profiles_dict[email_key]
                    if not existing.get("cargo") and sp.cargo:
                        existing["cargo"] = sp.cargo
                else:
                    profiles_dict[email_key] = {
                        "id": str(sp.id),
                        "profileName": sp.profile_name,
                        "nombre": sp.nombre or "",
                        "apellido": sp.apellido or "",
                        "cargo": sp.cargo or "",
                        "email": sp.email or "",
                        "celular": sp.celular or "",
                        "customFields": []
                    }
        except Exception as e_db:
            print(f"[WARN] Error cargando perfiles desde SQLite: {e_db}")
        finally:
            if close_db_local:
                active_db.close()

    # 4. Asegurar que perfiles conocidos tengan cargo representativo
    for key, p in profiles_dict.items():
        em = (p.get("email") or "").lower()
        if "guillermo.canon" in em and not p.get("cargo"):
            p["cargo"] = "Representante Legal / Gerente General"
        elif "kelly.delgado" in em and not p.get("cargo"):
            p["cargo"] = "Administración"

    result = list(profiles_dict.values())

    # 5. Guardar unificación en cache local para reinicios rápidos
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    except Exception as e_save:
        print(f"[WARN] Error actualizando cache de employer_profiles.json: {e_save}")

    return result

@app.post("/api/employer-profiles")
def update_employer_profiles(
    payload: List[Dict[str, Any]],
    request: Request = None,
    db = Depends(get_db)
):
    path = os.path.join(DATA_DIR, "employer_profiles.json")
    client_ip = request.client.host if (request and request.client) else None

    synced_list = []
    for item in payload:
        synced = sync_profile_to_supabase_and_local(item, db=db, client_ip=client_ip)
        synced_list.append(synced)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(synced_list, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Error guardando employer_profiles.json: {e}")

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

    # Enforce resolution via Supabase in production
    if APP_ENVIRONMENT == "production":
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Se requiere autenticación para resolver perfil comercial en entorno productivo."
            )
        try:
            user_client = get_supabase_user_client(token)
            res = user_client.table("profiles").select("*").eq("id", clean_id).eq("is_active", True).single().execute()
            if not res.data:
                raise HTTPException(
                    status_code=404,
                    detail=f"El responsable comercial '{clean_id}' no existe o está inactivo en Supabase."
                )
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
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error consultando perfiles comerciales en Supabase: {str(e)}"
            )

    # In non-production (local/staging), try Supabase first, fallback to SQLite
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

def get_current_authenticated_profile(request: Request, db = Depends(get_db)) -> CommercialProfile:
    """Verifies HttpOnly cookie session or Authorization header for authenticated user access."""
    token = request.cookies.get("admin_session")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(status_code=401, detail="Sesión no encontrada o credenciales requeridas.")

    payload = None
    try:
        supa_payload = decode_supabase_jwt(token)
        app_meta = supa_payload.get("app_metadata") or {}
        payload = {
            "email": supa_payload.get("email"),
            "role": app_meta.get("role") or supa_payload.get("role")
        }
    except Exception:
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

def get_current_admin_user(request: Request, db = Depends(get_db)):
    """Verifies HttpOnly cookie session or Authorization header for admin access."""
    user = get_current_authenticated_profile(request, db)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado: se requieren permisos de administrador.")
    return user

@app.get("/api/commercial-profiles")
def list_commercial_profiles_public(request: Request, db = Depends(get_db)):
    """
    Retorna catálogo público de perfiles comerciales activos.
    Si se presenta un token de Supabase y la RPC retorna perfiles (> 0), los retorna respetando RLS.
    Si no, consulta SQLite y retorna todos los perfiles comerciales activos para selección y autollenado.
    """
    token = request.cookies.get("admin_session")
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]

    if token:
        try:
            user_client = get_supabase_user_client(token)
            res = user_client.rpc("get_company_commercial_profiles").execute()
            if res.data and len(res.data) > 0:
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

    query = db.query(CommercialProfile).filter(CommercialProfile.is_active == True)
    rows = query.order_by(CommercialProfile.profile_name.asc()).all()
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
async def get_company_data_rls(user: Dict[str, Any] = Depends(get_current_user)):
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
    site_url = os.getenv("SITE_URL", "https://autoform.iaclatam.com").rstrip("/")
    try:
        link_res = admin_client.auth.admin.generate_link({
            "type": "recovery",
            "email": email_clean,
            "options": {
                "redirect_to": f"{site_url}/auth/reset-password"
            }
        })
        if hasattr(link_res, "properties") and link_res.properties:
            action_link = getattr(link_res.properties, "action_link", None) or link_res.properties.get("action_link")
    except Exception as e:
        print(f"[WARNING] Could not generate activation recovery link: {e}")

    # In production: invitation is sent directly via corporate SMTP; action_link is NOT exposed
    if APP_ENVIRONMENT == "production":
        return {
            "status": "success",
            "user_id": new_user_res.user.id,
            "email": email_clean,
            "role": dto.role,
            "message": f"Invitación enviada exitosamente por correo corporativo a {email_clean}."
        }

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
    user_id = str(user["id"])
    client = user.get("user_client")
    if not client:
        try:
            client = get_supabase_admin_client()
        except Exception:
            pass
    if not client:
        raise HTTPException(status_code=500, detail="Cliente de almacenamiento no disponible.")

    try:
        hist_res = client.table("form_fill_history").select("operator_user_id,output_storage_path").eq("id", history_id).limit(1).execute()
        if not hist_res.data or len(hist_res.data) == 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado o registro no autorizado.")
        row = hist_res.data[0]
        if str(row.get("operator_user_id")) != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado: no tienes permisos para acceder a este registro.")
        path = row.get("output_storage_path")
        if not path:
            raise HTTPException(status_code=404, detail="Registro de llenado sin PDF generado.")
        b_name, b_key = parse_storage_path(path)
        signed = client.storage.from_("generated-pdfs").create_signed_url(b_key, expires_in=3600)
        url = signed.get("signedURL") or signed.get("signedUrl")
        return {"signed_url": url, "storage_path": path}
    except HTTPException:
        raise
    except Exception as e:
        if "PGRST116" in str(e) or "0 rows" in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado o registro no autorizado.")
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

class RegistrationRateLimiter:
    """Sliding window in-memory rate limiter for user registration."""
    def __init__(self, max_requests: int = 5, window_seconds: int = 900): # 5 attempts per 15 min
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.attempts: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        self.attempts[client_ip] = [ts for ts in self.attempts[client_ip] if ts > cutoff]
        if len(self.attempts[client_ip]) >= self.max_requests:
            return False
        self.attempts[client_ip].append(now)
        return True

    def reset(self, client_ip: Optional[str] = None):
        if client_ip:
            self.attempts.pop(client_ip, None)
        else:
            self.attempts.clear()

registration_rate_limiter = RegistrationRateLimiter()

CORPORATE_EMAIL_REGEX = re.compile(r"^[^@\s]+@(iaclatam\.com|iac\.com\.co)$", re.IGNORECASE)
NAME_REGEX = re.compile(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$")
CARGO_REGEX = re.compile(r"^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s\.\-]+$")
CIUDAD_REGEX = re.compile(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\.\-]+$")

check_email_rate_limiter = RegistrationRateLimiter(max_requests=10, window_seconds=60)

@app.get("/api/auth/check-email")
def check_email_availability(email: str, request: Request, db = Depends(get_db)):
    """Verifica si un correo electrónico ya está registrado en la base de datos."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not check_email_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Límite de consultas de verificación de correo excedido. Por favor intenta de nuevo más tarde."
        )

    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        return {"available": False, "exists": False, "message": "Formato de correo no válido"}
    existing = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(email_clean)).first()
    return {"available": existing is None, "exists": existing is not None}

@app.post("/api/auth/register")
def auth_register(dto: CommercialRegisterDTO, request: Request, response: Response, db = Depends(get_db)):
    """Registra un nuevo responsable comercial individual y abre su sesión de inmediato."""
    client_ip = request.client.host if request.client else "127.0.0.1"

    # 1. Rate Limiting: máximo 5 intentos por ventana de 15 minutos por IP
    if not registration_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Límite de intentos de registro excedido. Por favor intenta de nuevo más tarde."
        )

    # 2. Correo Corporativo y Unicidad en Base de Datos (normalización trim + lowercase)
    email_clean = dto.email.strip().lower()
    if not email_clean or not CORPORATE_EMAIL_REGEX.match(email_clean):
        raise HTTPException(
            status_code=400,
            detail="Dominio de correo no autorizado. Solo se permiten cuentas corporativas @iaclatam.com o @iac.com.co."
        )

    existing = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(email_clean)).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"El correo electrónico '{email_clean}' ya se encuentra registrado. Por favor utiliza otro correo o inicia sesión."
        )

    # 3. Nombres y Apellidos: letras, tildes y espacios; mínimo 4 caracteres en cada uno
    nombre_clean = dto.nombre.strip()
    apellido_clean = dto.apellido.strip()
    if len(nombre_clean) < 4:
        raise HTTPException(status_code=400, detail="El nombre debe tener al menos 4 caracteres.")
    if not NAME_REGEX.match(nombre_clean):
        raise HTTPException(status_code=400, detail="El nombre debe contener únicamente letras y espacios.")

    if len(apellido_clean) < 4:
        raise HTTPException(status_code=400, detail="El apellido debe tener al menos 4 caracteres.")
    if not NAME_REGEX.match(apellido_clean):
        raise HTTPException(status_code=400, detail="El apellido debe contener únicamente letras y espacios.")

    # 4. Cargo: texto alfanumérico y espacios; mínimo 5 caracteres
    cargo_clean = dto.cargo.strip()
    if len(cargo_clean) < 5:
        raise HTTPException(status_code=400, detail="El cargo debe tener al menos 5 caracteres.")
    if not CARGO_REGEX.match(cargo_clean):
        raise HTTPException(status_code=400, detail="El cargo contiene caracteres no permitidos.")

    # 5. Celular: numérico estricto y exactamente 10 dígitos
    celular_clean = dto.celular.strip()
    if not celular_clean.isdigit() or len(celular_clean) != 10:
        raise HTTPException(status_code=400, detail="El número de celular debe ser numérico y contener exactamente 10 dígitos.")

    # 6. Cédula: numérico estricto y entre 8 y 11 dígitos
    documento_clean = dto.documento_identidad.strip() if dto.documento_identidad else ""
    if not documento_clean.isdigit() or not (8 <= len(documento_clean) <= 11):
        raise HTTPException(status_code=400, detail="El número de cédula debe ser numérico y contener entre 8 y 11 dígitos.")

    # 7. Ciudad: letras, tildes, espacios, punto y guion; mínimo 3 caracteres
    ciudad_clean = dto.ciudad.strip() if dto.ciudad else ""
    if not ciudad_clean or len(ciudad_clean) < 3:
        raise HTTPException(status_code=400, detail="La ciudad es obligatoria y debe tener al menos 3 caracteres.")
    if not CIUDAD_REGEX.match(ciudad_clean):
        raise HTTPException(status_code=400, detail="La ciudad debe contener únicamente letras, espacios, punto o guion.")

    # 8. Contraseña: mínimo 8 caracteres (nunca registrar en logs ni devolver)
    password_clean = dto.password.strip()
    if len(password_clean) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres.")

    # 9. Valores de seguridad impuestos por el backend (nunca aceptados del payload)
    enforced_role = "commercial"
    enforced_is_active = True

    # 10. Supabase Auth Administrativo (Fase 1: crear usuario antes de persistir perfil)
    admin_client = None
    try:
        admin_client = get_supabase_admin_client()
    except Exception:
        admin_client = None

    auth_user_id = None
    if admin_client:
        resolved_company_id = os.getenv("DEFAULT_COMPANY_ID")
        if not resolved_company_id:
            try:
                comp_res = admin_client.table("companies").select("id").eq("is_active", True).limit(1).execute()
                if comp_res.data and len(comp_res.data) > 0:
                    resolved_company_id = comp_res.data[0]["id"]
            except Exception:
                pass

        auth_payload = {
            "email": email_clean,
            "password": password_clean,
            "email_confirm": True,
            "app_metadata": {
                "role": enforced_role,
                "is_active": enforced_is_active
            },
            "user_metadata": {
                "nombre": nombre_clean,
                "apellido": apellido_clean,
                "cargo": cargo_clean,
                "celular": celular_clean,
                "ciudad": ciudad_clean,
                "tipo_documento": dto.tipo_documento or "CC",
                "documento_identidad": documento_clean
            }
        }
        if resolved_company_id:
            auth_payload["app_metadata"]["company_id"] = str(resolved_company_id)

        try:
            auth_res = admin_client.auth.admin.create_user(auth_payload)
            auth_user = getattr(auth_res, "user", None) or auth_res
            auth_user_id = str(getattr(auth_user, "id", None) or (auth_user.get("id") if isinstance(auth_user, dict) else None))
        except Exception as e:
            # Si falla la creación en Supabase Auth, se detiene de inmediato: no se persiste perfil
            raise HTTPException(
                status_code=400,
                detail=f"Error al registrar usuario en Supabase Auth: {str(e)}"
            )

    # 11. Persistencia de Perfil en Base de Datos (Fase 2)
    try:
        profile_id = auth_user_id if auth_user_id else str(uuid.uuid4())
        pwd_hash = hash_password(password_clean)
        display_name = dto.profile_name.strip() if (dto.profile_name and dto.profile_name.strip()) else f"{nombre_clean} {apellido_clean}"

        new_profile = CommercialProfile(
            id=profile_id,
            profile_name=display_name,
            nombre=nombre_clean,
            apellido=apellido_clean,
            cargo=cargo_clean or "Asesor Comercial",
            email=email_clean,
            celular=celular_clean,
            ciudad=ciudad_clean,
            tipo_documento=dto.tipo_documento or "CC",
            documento_identidad=documento_clean,
            role=enforced_role,
            password_hash=pwd_hash,
            is_active=enforced_is_active,
            last_modified_by_ip=client_ip
        )
        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)
    except Exception as db_err:
        db.rollback()
        # COMPENSACIÓN SEGURA: Si falla la persistencia después de crear el usuario Auth,
        # eliminar el usuario de Supabase Auth para evitar una cuenta huérfana
        if admin_client and auth_user_id:
            try:
                admin_client.auth.admin.delete_user(auth_user_id)
            except Exception as comp_err:
                print(f"[SECURITY ALERT] Fallo al compensar y eliminar usuario huérfano de Auth {auth_user_id}: {comp_err}")
        raise HTTPException(
            status_code=500,
            detail="Error al persistir el perfil comercial en la base de datos."
        )

    # 12. Emisión de sesión directa (sin aprobación manual ni estados pendientes)
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
        "ciudad": new_profile.ciudad,
        "token": token
    }


forgot_password_rate_limiter = RegistrationRateLimiter(max_requests=3, window_seconds=900)

def get_client_ip(request: Request) -> str:
    """Extrae la IP real del cliente respetando proxies reversos (Render, Cloudflare, Nginx)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

def extract_supabase_user_info(res: Any) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
    """Extrae de forma robusta (id, email, metadata) de un User o UserResponse de Supabase."""
    if not res:
        return None, None, None
    target = getattr(res, "user", None) or res
    user_id = str(getattr(target, "id", None) or "") or None
    user_email = getattr(target, "email", None)
    if not isinstance(user_email, str):
        nested = getattr(target, "user", None)
        if nested and isinstance(getattr(nested, "email", None), str):
            user_email = nested.email
            if not user_id:
                user_id = str(getattr(nested, "id", None) or "")
    meta = getattr(target, "user_metadata", {}) or {}
    if not isinstance(meta, dict):
        meta = {}
    return user_id, user_email if isinstance(user_email, str) else None, meta

def find_user_for_password_reset(db, email_clean: str) -> Optional[Tuple[str, str, str]]:
    """
    Busca al usuario por correo normalizado (trim + lowercase):
    1. En la base de datos relacional (CommercialProfile).
    2. Fallback autoritativo en Supabase Auth (auth.users).
    Retorna (user_id, display_name, canonical_email) o None.
    """
    # 1. Búsqueda en CommercialProfile (activo)
    user_profile = db.query(CommercialProfile).filter(
        CommercialProfile.email.ilike(email_clean),
        CommercialProfile.is_active == True
    ).first()

    if user_profile:
        display_name = user_profile.nombre or user_profile.profile_name or "Usuario Comercial"
        return (str(user_profile.id), display_name, user_profile.email.strip().lower())

    # 2. Fallback autoritativo en Supabase Auth
    try:
        admin_client = get_supabase_admin_client()
        if admin_client:
            page = 1
            while True:
                users_batch = admin_client.auth.admin.list_users(page=page, per_page=100)
                if not users_batch:
                    break
                for u in users_batch:
                    _, u_email, u_meta = extract_supabase_user_info(u)
                    if u_email and u_email.strip().lower() == email_clean:
                        nombre = u_meta.get("nombre", "") if u_meta else ""
                        apellido = u_meta.get("apellido", "") if u_meta else ""
                        disp_name = f"{nombre} {apellido}".strip() or email_clean.split("@")[0]
                        u_id = str(getattr(u, "id", None) or "")
                        return (u_id, disp_name, u_email.strip().lower())
                if len(users_batch) < 100:
                    break
                page += 1
    except Exception as e:
        print(f"[RESET] [WARN] Error en búsqueda de usuario en Supabase Auth: {type(e).__name__}: {e}", flush=True)

    return None

@app.post("/api/auth/forgot-password")
def forgot_password(dto: ForgotPasswordRequestDTO, request: Request, db = Depends(get_db)):
    """
    Solicitud de recuperación de contraseña con respuesta ciega anti-enumeración,
    generación de token SHA-256 de un solo uso, búsqueda federada y despacho síncrono vía SMTP corporativo.
    """
    client_ip = get_client_ip(request)
    print("[RESET] request_received", flush=True)

    if not forgot_password_rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Límite de solicitudes de recuperación excedido. Por favor intenta de nuevo en 15 minutos."
        )

    email_clean = (dto.email or "").strip().lower()
    if not email_clean or "@" not in email_clean:
        print("[RESET] user_found=false", flush=True)
        time.sleep(0.35)
        return {
            "status": "success",
            "message": "Si la dirección ingresada corresponde a un usuario corporativo registrado, recibirá un enlace seguro con las instrucciones de acceso."
        }

    user_info = find_user_for_password_reset(db, email_clean)
    if not user_info:
        print("[RESET] user_found=false", flush=True)
        time.sleep(0.35)
        return {
            "status": "success",
            "message": "Si la dirección ingresada corresponde a un usuario corporativo registrado, recibirá un enlace seguro con las instrucciones de acceso."
        }

    user_id, display_name, canonical_email = user_info
    print("[RESET] user_found=true", flush=True)

    # Exclusivamente el correo digitado por el usuario en el formulario (trim + lowercase)
    target_recipient = email_clean
    print(f"[RESET] recipient={mask_email(target_recipient)}", flush=True)

    provider = get_email_provider()
    print(f"[RESET] provider={provider}", flush=True)

    if provider == "microsoft_graph":
        cfg = get_graph_config()
        has_tenant = bool(os.getenv("MS_TENANT_ID", "").strip())
        has_client_id = bool(os.getenv("MS_CLIENT_ID", "").strip())
        has_secret = bool(os.getenv("MS_CLIENT_SECRET", "").strip())
        has_sender = bool(os.getenv("MAIL_SENDER", "").strip())
        missing_vars = get_missing_graph_vars()
        is_graph_configured = len(missing_vars) == 0

        print(
            f"[RESET] graph_configured={str(is_graph_configured).lower()} "
            f"(tenant={has_tenant}, client_id={has_client_id}, secret={has_secret}, sender={has_sender})",
            flush=True
        )

        try:
            if not is_graph_configured:
                print(f"[RESET] [GRAPH_CONFIG_ERROR] Variables requeridas no configuradas: {', '.join(missing_vars)}", flush=True)
                raise RuntimeError(f"Configuración Microsoft Graph incompleta. Faltan variables requeridas: {', '.join(missing_vars)}")

            now_utc = datetime.now(timezone.utc)
            # 1. Invalidar cualquier token activo previo para este usuario
            db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None)
            ).update({"used_at": now_utc}, synchronize_session=False)

            # 2. Generar token criptográfico y almacenar su hash SHA-256
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            expires_at = now_utc + timedelta(minutes=15)

            new_token_record = PasswordResetToken(
                id=str(uuid.uuid4()),
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
                request_ip=client_ip
            )
            db.add(new_token_record)
            db.commit()

            # 3. Construir enlace de restablecimiento
            site_url = cfg["site_url"]
            reset_link = f"{site_url}/?token={raw_token}"

            # 4. Despacho síncrono del correo vía Microsoft Graph
            send_password_reset_email(
                recipient_email=target_recipient,
                recipient_name=display_name,
                reset_link=reset_link
            )
            print("[RESET] email_sent=true", flush=True)

        except Exception as err:
            try:
                db.rollback()
                if 'new_token_record' in locals() and hasattr(new_token_record, 'id') and new_token_record.id:
                    db.query(PasswordResetToken).filter(PasswordResetToken.id == new_token_record.id).update(
                        {"used_at": datetime.now(timezone.utc)}, synchronize_session=False
                    )
                    db.commit()
            except Exception:
                pass

            exc_type = type(err).__name__
            tb_safe = traceback.format_exc()
            safe_err = sanitize_safe_log(str(err), os.getenv("MS_CLIENT_SECRET", "").strip())
            safe_tb = sanitize_safe_log(tb_safe, os.getenv("MS_CLIENT_SECRET", "").strip())
            print(f"[RESET] graph_send_failed: {exc_type}: {safe_err}\n{safe_tb}", flush=True)

    else:
        # Soporte a SMTP corporativo
        cfg = get_smtp_config()
        has_host = bool(os.getenv("SMTP_HOST", "").strip())
        has_port = bool(os.getenv("SMTP_PORT", "").strip())
        has_user = bool(os.getenv("SMTP_USER", "").strip())
        has_password = bool(os.getenv("SMTP_PASSWORD", "").strip())
        missing_vars = get_missing_smtp_vars()
        is_smtp_configured = len(missing_vars) == 0

        print(
            f"[RESET] smtp_configured={str(is_smtp_configured).lower()} "
            f"(host={has_host}, port={has_port}, user={has_user}, password={has_password})",
            flush=True
        )

        try:
            if not is_smtp_configured:
                print(f"[RESET] [SMTP_CONFIG_ERROR] Variables requeridas no configuradas: {', '.join(missing_vars)}", flush=True)
                raise RuntimeError(f"Configuración SMTP incompleta. Faltan variables requeridas: {', '.join(missing_vars)}")

            now_utc = datetime.now(timezone.utc)
            # 1. Invalidar cualquier token activo previo para este usuario
            db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None)
            ).update({"used_at": now_utc}, synchronize_session=False)

            # 2. Generar token criptográfico y almacenar su hash SHA-256
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            expires_at = now_utc + timedelta(minutes=15)

            new_token_record = PasswordResetToken(
                id=str(uuid.uuid4()),
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
                request_ip=client_ip
            )
            db.add(new_token_record)
            db.commit()

            # 3. Construir enlace de restablecimiento
            site_url = cfg["site_url"]
            reset_link = f"{site_url}/?token={raw_token}"

            # 4. Despacho síncrono del correo
            send_password_reset_email(
                recipient_email=target_recipient,
                recipient_name=display_name,
                reset_link=reset_link
            )
            print("[RESET] email_sent=true", flush=True)

        except Exception as err:
            try:
                db.rollback()
                if 'new_token_record' in locals() and hasattr(new_token_record, 'id') and new_token_record.id:
                    db.query(PasswordResetToken).filter(PasswordResetToken.id == new_token_record.id).update(
                        {"used_at": datetime.now(timezone.utc)}, synchronize_session=False
                    )
                    db.commit()
            except Exception:
                pass

            exc_type = type(err).__name__
            tb_safe = traceback.format_exc()
            print(f"[RESET] smtp_send_failed: {exc_type}: {str(err)}\n{tb_safe}", flush=True)

    return {
        "status": "success",
        "message": "Si la dirección ingresada corresponde a un usuario corporativo registrado, recibirá un enlace seguro con las instrucciones de acceso."
    }

@app.get("/api/auth/verify-reset-token", response_model=VerifyResetTokenResponseDTO)
def verify_reset_token(token: str, db = Depends(get_db)):
    """Verificación temprana del estado del token sin consumirlo."""
    raw_token = token.strip() if token else ""
    if not raw_token or len(raw_token) < 16:
        raise HTTPException(
            status_code=400,
            detail="El token de recuperación proporcionado no es válido."
        )

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash
    ).first()

    if not record or record.used_at is not None:
        raise HTTPException(
            status_code=400,
            detail="El enlace de recuperación es inválido o ya ha sido utilizado. Por favor solicita uno nuevo."
        )

    now_utc = datetime.now(timezone.utc)
    exp = record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now_utc:
        raise HTTPException(
            status_code=400,
            detail="El enlace de recuperación ha expirado (vigencia de 15 minutos). Por favor solicita uno nuevo."
        )

    user = db.query(CommercialProfile).filter(
        CommercialProfile.id == record.user_id,
        CommercialProfile.is_active == True
    ).first()

    masked = None
    if user:
        masked = mask_email(user.email)
    else:
        # Fallback a Supabase Auth si el perfil comercial aún no se ha sincronizado
        try:
            admin_client = get_supabase_admin_client()
            if admin_client:
                res = admin_client.auth.admin.get_user_by_id(record.user_id)
                _, u_email, _ = extract_supabase_user_info(res)
                if u_email:
                    masked = mask_email(u_email)
        except Exception as e:
            print(f"[RESET] [WARN] Error verificando usuario en Supabase Auth: {type(e).__name__}: {e}", flush=True)

    if not masked:
        raise HTTPException(
            status_code=400,
            detail="El usuario asociado a este enlace ya no se encuentra activo."
        )

    return VerifyResetTokenResponseDTO(
        valid=True,
        masked_email=masked,
        message="Token válido."
    )

@app.post("/api/auth/reset-password")
def reset_password(dto: ResetPasswordRequestDTO, db = Depends(get_db)):
    """
    Restablece la contraseña corporativa invalidando el token,
    actualizando como fuente primaria Supabase Auth y sincronizando el hash relacional.
    """
    # 1. Validación de fortaleza de contraseña
    password_clean = dto.password.strip()
    if len(password_clean) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres.")
    if not any(c.isupper() for c in password_clean) or not any(c.islower() for c in password_clean):
        raise HTTPException(status_code=400, detail="La contraseña debe contener al menos una mayúscula y una minúscula.")
    if not any(c.isdigit() or c in "!@#$%^&*()_+-=[]{};':\"|,.<>/?" for c in password_clean):
        raise HTTPException(status_code=400, detail="La contraseña debe contener al menos un número o símbolo.")

    # 2. Verificación de token
    raw_token = dto.token.strip() if dto.token else ""
    if not raw_token or len(raw_token) < 16:
        raise HTTPException(status_code=400, detail="Token de recuperación inválido.")

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    record = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash
    ).first()

    if not record or record.used_at is not None:
        raise HTTPException(
            status_code=400,
            detail="El enlace de recuperación es inválido o ya ha sido utilizado."
        )

    now_utc = datetime.now(timezone.utc)
    exp = record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now_utc:
        raise HTTPException(
            status_code=400,
            detail="El enlace de recuperación ha expirado. Por favor solicita uno nuevo."
        )

    user = db.query(CommercialProfile).filter(
        CommercialProfile.id == record.user_id,
        CommercialProfile.is_active == True
    ).first()

    admin_client = None
    try:
        admin_client = get_supabase_admin_client()
    except Exception:
        admin_client = None

    auth_user_id = None
    auth_user_email = None
    auth_user_meta = {}
    if admin_client:
        try:
            res = admin_client.auth.admin.get_user_by_id(record.user_id)
            auth_user_id, auth_user_email, auth_user_meta = extract_supabase_user_info(res)
        except Exception as e:
            print(f"[RESET] [WARN] Error obteniendo usuario en Supabase Auth: {type(e).__name__}: {e}", flush=True)

    if not user and not auth_user_email:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o inactivo.")

    # 3. Consumir token inmediatamente (One-Time Use)
    record.used_at = now_utc
    db.commit()

    # 4. Actualización en Supabase Auth como autoridad primaria
    if admin_client:
        try:
            admin_client.auth.admin.update_user_by_id(record.user_id, {"password": password_clean})
        except Exception as supa_err:
            print(f"[SUPABASE_AUTH_ERROR] Error al actualizar usuario {record.user_id} en Supabase Auth: {supa_err}", flush=True)
            record.used_at = None
            db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Error al sincronizar con el proveedor de autenticación: {str(supa_err)}"
            )

    # 5. Sincronización posterior de hash en PostgreSQL/SQLite
    try:
        if user:
            user.password_hash = hash_password(password_clean)
            if hasattr(user, "needs_password_hash_sync"):
                user.needs_password_hash_sync = False
            db.commit()
        elif auth_user_email:
            meta = auth_user_meta or {}
            new_cp = CommercialProfile(
                id=str(record.user_id),
                profile_name=f"{meta.get('nombre', '')} {meta.get('apellido', '')}".strip() or auth_user_email.split('@')[0],
                nombre=meta.get("nombre") or auth_user_email.split('@')[0],
                apellido=meta.get("apellido") or "",
                cargo=meta.get("cargo") or "Asesor Comercial",
                email=auth_user_email.strip().lower(),
                celular=meta.get("celular") or "3000000000",
                password_hash=hash_password(password_clean),
                role=meta.get("role") or "commercial",
                is_active=True
            )
            db.add(new_cp)
            db.commit()
    except Exception as db_err:
        db.rollback()
        print(f"[CREDENTIAL_SYNC_ERROR] Fallo al sincronizar hash local para usuario {record.user_id}: {db_err}", flush=True)

    return {
        "status": "success",
        "message": "Tu contraseña corporativa ha sido actualizada exitosamente."
    }


@app.get("/api/admin/check")
@app.get("/api/auth/check")
def admin_check(request: Request, db = Depends(get_db)):
    try:
        user = get_current_authenticated_profile(request, db)
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
def list_commercial_profiles_admin(current_user: CommercialProfile = Depends(get_current_authenticated_profile), db = Depends(get_db)):
    rows = db.query(CommercialProfile).order_by(CommercialProfile.created_at.desc()).all()
    return [CommercialProfileAdminDTO(**r.to_admin_dict()) for r in rows]

@app.post("/api/admin/commercial-profiles", response_model=CommercialProfileAdminDTO)
def create_commercial_profile(
    dto: CommercialProfileCreateDTO,
    request: Request,
    current_user: CommercialProfile = Depends(get_current_authenticated_profile),
    db = Depends(get_db)
):
    existing = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(dto.email.strip())).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Ya existe un perfil con el correo {dto.email}")

    client_ip = request.client.host if request.client else None
    assigned_role = dto.role if (current_user.role == "admin" and dto.role) else "commercial"

    profile_data = {
        "profile_name": dto.profile_name.strip(),
        "nombre": dto.nombre.strip(),
        "apellido": dto.apellido.strip(),
        "cargo": dto.cargo.strip(),
        "email": dto.email.strip().lower(),
        "celular": dto.celular.strip(),
        "ciudad": dto.ciudad.strip() if dto.ciudad else None,
        "tipo_documento": dto.tipo_documento or "C.C",
        "documento_identidad": dto.documento_identidad.strip() if dto.documento_identidad else None,
        "role": assigned_role or "commercial",
        "password": dto.password
    }

    synced = sync_profile_to_supabase_and_local(profile_data, db=db, client_ip=client_ip)

    new_profile = db.query(CommercialProfile).filter(CommercialProfile.id == synced["id"]).first()
    if not new_profile:
        new_profile = db.query(CommercialProfile).filter(CommercialProfile.email.ilike(dto.email.strip())).first()

    if new_profile and dto.password:
        new_profile.password_hash = hash_password(dto.password)
        db.commit()
        db.refresh(new_profile)

    # Actualizar cache local en employer_profiles.json
    try:
        path = os.path.join(DATA_DIR, "employer_profiles.json")
        saved = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                saved = json.load(f) or []
        updated = False
        for i, p in enumerate(saved):
            if (p.get("email") or "").lower() == dto.email.strip().lower():
                saved[i] = synced
                updated = True
                break
        if not updated:
            saved.append(synced)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(saved, f, indent=2, ensure_ascii=False)
    except Exception as e_cache:
        print(f"[WARN] Error actualizando employer_profiles.json en create_commercial_profile: {e_cache}")

    return CommercialProfileAdminDTO(**new_profile.to_admin_dict())

@app.put("/api/admin/commercial-profiles/{profile_id}", response_model=CommercialProfileAdminDTO)
def update_commercial_profile(
    profile_id: str,
    dto: CommercialProfileUpdateDTO,
    request: Request,
    current_user: CommercialProfile = Depends(get_current_authenticated_profile),
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
    if dto.ciudad is not None: profile.ciudad = dto.ciudad.strip()
    if dto.tipo_documento is not None: profile.tipo_documento = dto.tipo_documento
    if dto.documento_identidad is not None: profile.documento_identidad = dto.documento_identidad.strip()
    if dto.is_active is not None and current_user.role == "admin": profile.is_active = dto.is_active
    if dto.password:
        profile.password_hash = hash_password(dto.password)
        try:
            admin_client = get_supabase_admin_client()
            if admin_client:
                try:
                    admin_client.auth.admin.update_user_by_id(profile.id, {"password": dto.password})
                except Exception:
                    try:
                        for u in admin_client.auth.admin.list_users(page=1, per_page=1000):
                            if (u.email or "").lower() == profile.email.lower():
                                admin_client.auth.admin.update_user_by_id(u.id, {"password": dto.password})
                                break
                    except Exception as e_supa:
                        print(f"[WARN] Error actualizando clave en Supabase Auth: {e_supa}")
        except Exception:
            pass

    # Sincronizar actualización de campos en Supabase public.profiles
    try:
        admin_client = get_supabase_admin_client()
        if admin_client:
            supa_fields = {}
            if dto.cargo is not None: supa_fields["cargo"] = dto.cargo.strip()
            if dto.nombre is not None: supa_fields["nombre"] = dto.nombre.strip()
            if dto.apellido is not None: supa_fields["apellido"] = dto.apellido.strip()
            if dto.profile_name is not None: supa_fields["display_name"] = dto.profile_name.strip()
            if dto.celular is not None: supa_fields["celular"] = dto.celular.strip()
            if dto.ciudad is not None: supa_fields["ciudad"] = dto.ciudad.strip()
            if dto.tipo_documento is not None: supa_fields["tipo_documento"] = dto.tipo_documento
            if dto.documento_identidad is not None: supa_fields["documento_identidad"] = dto.documento_identidad.strip()
            if dto.is_active is not None: supa_fields["is_active"] = dto.is_active
            if supa_fields:
                try:
                    admin_client.table("profiles").update(supa_fields).eq("id", profile.id).execute()
                except Exception:
                    admin_client.table("profiles").update(supa_fields).eq("email", profile.email).execute()
    except Exception as e_supa_up:
        print(f"[WARN] Error actualizando public.profiles en Supabase: {e_supa_up}")

    db.commit()
    db.refresh(profile)

    # Actualizar employer_profiles.json cache
    try:
        path = os.path.join(DATA_DIR, "employer_profiles.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                saved = json.load(f) or []
            for i, p in enumerate(saved):
                if p.get("id") == profile.id or (p.get("email") or "").lower() == profile.email.lower():
                    saved[i]["profileName"] = profile.profile_name
                    saved[i]["nombre"] = profile.nombre
                    saved[i]["apellido"] = profile.apellido
                    saved[i]["cargo"] = profile.cargo
                    saved[i]["celular"] = profile.celular
                    break
            with open(path, "w", encoding="utf-8") as f:
                json.dump(saved, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

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

    # Desactivar también en Supabase
    try:
        admin_client = get_supabase_admin_client()
        if admin_client:
            try:
                admin_client.table("profiles").update({"is_active": False}).eq("id", profile_id).execute()
            except Exception:
                admin_client.table("profiles").update({"is_active": False}).eq("email", profile.email).execute()
    except Exception as e_supa_del:
        print(f"[WARN] Error desactivando en Supabase: {e_supa_del}")

    # Remover o marcar inactivo en employer_profiles.json
    try:
        path = os.path.join(DATA_DIR, "employer_profiles.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                saved = json.load(f) or []
            saved = [p for p in saved if p.get("id") != profile_id and (p.get("email") or "").lower() != profile.email.lower()]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(saved, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return {"status": "success", "message": f"Perfil {profile.profile_name} desactivado."}


def normalize_form_tokens(text: str) -> Set[str]:
    if not text:
        return set()
    t = text.lower()
    if t.endswith(".pdf"):
        t = t[:-4]
    t = t.replace("\ufffd", " ")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    tokens = set(re.findall(r"[a-z0-9]+", t))
    return {tok for tok in tokens if len(tok) > 1 or tok.isdigit()}


def match_template_score(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    matches = 0
    for ta in tokens_a:
        for tb in tokens_b:
            if ta == tb or (len(ta) >= 5 and len(tb) >= 5 and (ta.startswith(tb) or tb.startswith(ta))):
                matches += 1
                break
    return matches / max(len(tokens_a), len(tokens_b))


def resolve_or_provision_template_version(
    template_code: str,
    filename: Optional[str] = None,
    company_id: Optional[str] = None,
    admin_client: Optional[Any] = None,
    user_id: Optional[str] = None,
    page_count: int = 1,
    is_acroform: bool = False,
) -> Dict[str, Any]:
    """
    Resuelve el template_id institucional y template_version_id publicado para una plantilla dada.
    Soporta:
      1. Búsqueda exacta y coincidencia semántica/difusa tolerante a tildes, códigos y codificaciones.
      2. Si la plantilla existe en pdf_templates, obtiene la última versión 'published' en pdf_template_versions.
      3. Si no existe y se cuenta con admin_client y company_id, auto-aprovisiona la plantilla y su versión publicada.
    """
    default_result = {
        "is_institutional": False,
        "pdf_template_id": None,
        "template_version_id": None,
        "version": 1,
    }

    if not admin_client or not company_id or company_id == "local_company":
        return default_result

    clean_name = filename[:-4] if (filename and filename.lower().endswith(".pdf")) else (filename or template_code or "")

    try:
        res = (
            admin_client.table("pdf_templates")
            .select("id, codigo, nombre, is_active")
            .eq("company_id", company_id)
            .eq("is_active", True)
            .execute()
        )
        db_templates = res.data or []

        matched_template = None
        best_score = 0.0

        # 1. Intentar coincidencia exacta directa
        for t in db_templates:
            t_cod = t.get("codigo") or ""
            t_nom = t.get("nombre") or ""
            if template_code in (t_cod, t_nom) or clean_name in (t_cod, t_nom):
                matched_template = t
                best_score = 1.0
                break

        # 2. Coincidencia tokenizada / semántica tolerante a acentos y reemplazos Unicode
        if not matched_template and db_templates:
            code_tokens = normalize_form_tokens(template_code)
            name_tokens = normalize_form_tokens(clean_name)
            target_tokens = code_tokens | name_tokens

            for t in db_templates:
                t_cod = t.get("codigo") or ""
                t_nom = t.get("nombre") or ""
                c_score = match_template_score(target_tokens, normalize_form_tokens(t_cod))
                n_score = match_template_score(target_tokens, normalize_form_tokens(t_nom))
                score = max(c_score, n_score)
                if score > best_score:
                    best_score = score
                    matched_template = t

            if best_score < 0.6:
                matched_template = None

        # 3. Si encontramos plantilla existente, resolver su versión publicada
        if matched_template:
            t_id = matched_template["id"]
            v_res = (
                admin_client.table("pdf_template_versions")
                .select("id, version, status, is_active")
                .eq("template_id", t_id)
                .eq("status", "published")
                .order("version", desc=True)
                .limit(1)
                .execute()
            )
            if v_res.data:
                ver = v_res.data[0]
                return {
                    "is_institutional": True,
                    "pdf_template_id": t_id,
                    "template_version_id": ver["id"],
                    "version": ver.get("version", 1),
                }

            # Si existe la plantilla pero su versión no está publicada, buscar versión activa
            v_active = (
                admin_client.table("pdf_template_versions")
                .select("id, version, status")
                .eq("template_id", t_id)
                .eq("is_active", True)
                .order("version", desc=True)
                .limit(1)
                .execute()
            )
            if v_active.data:
                ver = v_active.data[0]
                admin_client.table("pdf_template_versions").update({"status": "published"}).eq("id", ver["id"]).execute()
                return {
                    "is_institutional": True,
                    "pdf_template_id": t_id,
                    "template_version_id": ver["id"],
                    "version": ver.get("version", 1),
                }

        # 4. Si no existe en pdf_templates, auto-aprovisionar para el usuario/compañía
        safe_code = re.sub(r"[^A-Za-z0-9_-]", "_", clean_name)[:100].upper()
        if not safe_code:
            safe_code = f"TMPL_{uuid.uuid4().hex[:8].upper()}"

        new_tpl = admin_client.table("pdf_templates").insert({
            "company_id": company_id,
            "codigo": safe_code,
            "nombre": clean_name[:150] or safe_code,
            "is_active": True
        }).execute()

        if new_tpl.data and len(new_tpl.data) > 0:
            new_tpl_id = new_tpl.data[0]["id"]
            created_by_uuid = user_id if (user_id and len(user_id) == 36) else None
            new_ver = admin_client.table("pdf_template_versions").insert({
                "template_id": new_tpl_id,
                "version": 1,
                "filename": filename or f"{clean_name}.pdf",
                "storage_path": f"{company_id}/templates/{new_tpl_id}/v1/{filename or clean_name + '.pdf'}",
                "page_count": page_count,
                "is_acroform": is_acroform,
                "is_active": True,
                "status": "published",
                "created_by": created_by_uuid
            }).execute()

            if new_ver.data and len(new_ver.data) > 0:
                return {
                    "is_institutional": False,
                    "pdf_template_id": new_tpl_id,
                    "template_version_id": new_ver.data[0]["id"],
                    "version": 1,
                }

    except Exception as e:
        print(f"[WARN] Error in resolve_or_provision_template_version: {e}")

    return default_result


@app.get("/api/templates")
def list_templates(user: Dict[str, Any] = Depends(get_current_user)):
    user_id = str(user["id"])
    company_id = str(user.get("company_id") or "local_company")

    admin_client = None
    try:
        admin_client = get_supabase_admin_client()
    except Exception as e:
        print(f"[WARN] list_templates admin_client error: {e}")

    active_doc = None
    if admin_client:
        try:
            res = (
                admin_client.table("user_documents")
                .select("*")
                .eq("user_id", user_id)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            if res.data:
                active_doc = res.data[0]
        except Exception as e:
            print(f"[WARN] Error querying user_documents in Supabase: {e}")

    # Fallback local SQLite si no hay respuesta de Supabase (entorno dev/test)
    if not active_doc and APP_ENVIRONMENT != "production":
        db = SessionLocal()
        try:
            local_doc = (
                db.query(UserDocument)
                .filter(UserDocument.user_id == user_id, UserDocument.is_active == True)
                .first()
            )
            if local_doc:
                active_doc = local_doc.to_dict()
        finally:
            db.close()

    templates = []
    active_slot = None

    if active_doc:
        doc_id = str(active_doc.get("id"))
        template_code = active_doc.get("template_code") or doc_id
        filename = active_doc.get("filename", f"{template_code}.pdf")
        size_kb = float(active_doc.get("size_kb") or 0.0)

        res_info = resolve_or_provision_template_version(
            template_code=template_code,
            filename=filename,
            company_id=company_id,
            admin_client=admin_client,
            user_id=user_id,
            page_count=1,
            is_acroform=False
        )

        templates.append({
            "id": template_code,
            "document_id": doc_id,
            "template_id": res_info.get("pdf_template_id") or doc_id,
            "template_code": template_code,
            "filename": filename,
            "size_kb": size_kb,
            "is_active": True,
            "template_version_id": res_info.get("template_version_id"),
            "version": res_info.get("version", 1),
            "is_institutional": res_info.get("is_institutional", False)
        })
        active_slot = {
            "template_id": template_code,
            "document_id": doc_id,
            "filename": filename,
            "updated_at": active_doc.get("updated_at")
        }

    return {
        "templates": templates,
        "active_slot": active_slot
    }

@app.post("/api/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(get_current_user)
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Solo se admiten archivos PDF"
        )

    # 1. Validación en memoria mediante PyMuPDF (ADR-0011)
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=400,
            detail="El archivo PDF subido está vacío."
        )

    import fitz
    try:
        pdf_doc = fitz.open(stream=content, filetype="pdf")
        page_count = len(pdf_doc)
        is_acroform = any(bool(p.widgets()) for p in pdf_doc)
        pdf_doc.close()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Archivo PDF inválido o corrupto: {str(e)}"
        )

    # 2. Identificadores y rutas autoritativas
    user_id = str(user["id"])
    company_id = str(user.get("company_id") or "local_company")
    new_doc_id = str(uuid.uuid4())
    template_code = os.path.splitext(file.filename)[0]
    size_kb = round(len(content) / 1024, 1)

    admin_client = None
    try:
        admin_client = get_supabase_admin_client()
    except Exception as e:
        print(f"[WARN] Supabase admin client not available in upload_pdf: {e}")

    # Verificar coherencia de company_id si está disponible en Supabase
    if admin_client and (not company_id or company_id == "local_company"):
        try:
            prof_res = admin_client.table("profiles").select("company_id").eq("id", user_id).limit(1).execute()
            if prof_res.data and len(prof_res.data) > 0 and prof_res.data[0].get("company_id"):
                company_id = str(prof_res.data[0]["company_id"])
        except Exception:
            pass

    storage_bucket = "templates"
    storage_key = f"user_documents/{user_id}/{new_doc_id}.pdf"
    canonical_storage_path = f"templates/{storage_key}"

    # 3. Almacenamiento autoritativo en Supabase Storage (ADR-0011 Paso 1)
    if admin_client:
        try:
            admin_client.storage.from_(storage_bucket).upload(
                storage_key,
                content,
                file_options={"content-type": "application/pdf", "upsert": "true"}
            )
        except Exception as e:
            print(f"[ERROR] Error uploading to Supabase Storage: {e}")
            if APP_ENVIRONMENT == "production":
                raise HTTPException(
                    status_code=500,
                    detail=f"Fallo al persistir archivo en Supabase Storage: {str(e)}"
                )

    # 4. Transacción en Base de Datos (ADR-0011 Paso 2)
    superseded_docs = []

    if admin_client:
        try:
            prev_res = (
                admin_client.table("user_documents")
                .select("id,storage_path,filename")
                .eq("user_id", user_id)
                .eq("is_active", True)
                .execute()
            )
            if prev_res.data:
                superseded_docs = prev_res.data

            # Desactivar ranuras activas previas
            (
                admin_client.table("user_documents")
                .update({"is_active": False})
                .eq("user_id", user_id)
                .eq("is_active", True)
                .execute()
            )

            # Insertar nuevo registro activo
            insert_res = (
                admin_client.table("user_documents")
                .insert({
                    "id": new_doc_id,
                    "company_id": company_id,
                    "user_id": user_id,
                    "template_code": template_code,
                    "filename": file.filename,
                    "storage_path": canonical_storage_path,
                    "size_kb": size_kb,
                    "is_active": True
                })
                .execute()
            )
            if insert_res.data:
                new_doc_id = insert_res.data[0]["id"]
        except Exception as e:
            print(f"[ERROR] Error updating user_documents in Supabase: {e}")
            # COMPENSATING ROLLBACK (Saga Pattern):
            # 1. Eliminar archivo recién subido a Storage para prevenir artefactos huérfanos
            try:
                print(f"[COMPENSATION] Rolling back uploaded storage object: {storage_bucket}/{storage_key}")
                admin_client.storage.from_(storage_bucket).remove([storage_key])
            except Exception as se:
                print(f"[ERROR] Failed to execute compensating rollback on storage: {se}")

            # 2. Restaurar estado is_active = True para los documentos previamente desactivados
            if superseded_docs:
                for s_doc in superseded_docs:
                    s_id = s_doc.get("id")
                    if s_id:
                        try:
                            admin_client.table("user_documents").update({"is_active": True}).eq("id", s_id).execute()
                        except Exception as re_err:
                            print(f"[WARN] Failed to reactivate superseded doc {s_id}: {re_err}")

            if APP_ENVIRONMENT == "production":
                raise HTTPException(
                    status_code=500,
                    detail=f"Error registrando documento en base de datos: {str(e)}"
                )

    # Fallback/sync en SQLite local
    if APP_ENVIRONMENT != "production":
        db = SessionLocal()
        try:
            db.query(UserDocument).filter(
                UserDocument.user_id == user_id,
                UserDocument.is_active == True
            ).update({"is_active": False})

            local_rec = UserDocument(
                id=new_doc_id,
                company_id=company_id,
                user_id=user_id,
                template_code=template_code,
                filename=file.filename,
                storage_path=canonical_storage_path,
                size_kb=size_kb,
                is_active=True
            )
            db.add(local_rec)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[WARN] Local SQLite user_documents sync error: {e}")
        finally:
            db.close()

    # 5. Purga condicionada de documentos anteriores (ADR-0011 Paso 3)
    for prev_doc in superseded_docs:
        prev_id = prev_doc.get("id")
        prev_path = prev_doc.get("storage_path")
        prev_fn = prev_doc.get("filename")
        if not prev_id or prev_id == new_doc_id:
            continue

        can_delete = False
        if admin_client:
            try:
                rpc_res = admin_client.rpc(
                    "can_hard_delete_user_document",
                    {"p_doc_id": prev_id}
                ).execute()
                can_delete = bool(rpc_res.data)
            except Exception as e:
                print(f"[WARN] can_hard_delete_user_document error for {prev_id}: {e}")

        if can_delete:
            try:
                if admin_client and prev_path:
                    b_bucket, b_key = parse_storage_path(prev_path)
                    admin_client.storage.from_(b_bucket).remove([b_key])
                if admin_client:
                    admin_client.table("user_documents").delete().eq("id", prev_id).execute()
                if prev_fn:
                    prev_cache = os.path.join(INPUT_DIR, user_id, prev_fn)
                    if os.path.exists(prev_cache):
                        os.remove(prev_cache)
                if prev_id:
                    prev_uuid_cache = os.path.join(INPUT_DIR, user_id, f"{prev_id}.pdf")
                    if os.path.exists(prev_uuid_cache):
                        os.remove(prev_uuid_cache)
            except Exception as e:
                print(f"[WARN] Error executing hard-delete cleanup for {prev_id}: {e}")

    # 6. Escribir caché efímera local por usuario (input/{user_id}/{filename} y {doc_id}.pdf)
    user_cache_dir = os.path.join(INPUT_DIR, user_id)
    os.makedirs(user_cache_dir, exist_ok=True)
    user_cache_path = os.path.join(user_cache_dir, file.filename)
    user_cache_uuid_path = os.path.join(user_cache_dir, f"{new_doc_id}.pdf")
    try:
        with open(user_cache_path, "wb") as f:
            f.write(content)
        with open(user_cache_uuid_path, "wb") as f:
            f.write(content)
    except Exception as e:
        print(f"[WARN] Error writing user local cache: {e}")

    # 7. Vinculación autoritativa con plantillas institucionales o aprovisionamiento (ADR-0011)
    res_info = resolve_or_provision_template_version(
        template_code=template_code,
        filename=file.filename,
        company_id=company_id,
        admin_client=admin_client,
        user_id=user_id,
        page_count=page_count,
        is_acroform=is_acroform
    )

    # 8. Respuesta al frontend
    return {
        "status": "success",
        "template_id": template_code,
        "document_id": new_doc_id,
        "pdf_template_id": res_info.get("pdf_template_id"),
        "template_version_id": res_info.get("template_version_id"),
        "version": res_info.get("version", 1),
        "filename": file.filename,
        "size_kb": size_kb,
        "page_count": page_count,
        "is_acroform": is_acroform,
        "is_institutional": res_info.get("is_institutional", False),
        "is_active": True
    }

@app.delete("/api/templates/{template_id}")
def delete_template(
    template_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = str(user["id"])
    company_id = str(user.get("company_id") or "local_company")
    is_admin = user.get("role") == "admin"

    doc = resolve_user_document(user_id, template_id, is_admin=is_admin, company_id=company_id)
    doc_id = doc["id"]
    filename = doc["filename"]
    storage_path = doc.get("storage_path")

    admin_client = None
    try:
        admin_client = get_supabase_admin_client()
    except Exception:
        pass

    can_delete = False
    if admin_client:
        try:
            rpc_res = admin_client.rpc("can_hard_delete_user_document", {"p_doc_id": doc_id}).execute()
            can_delete = bool(rpc_res.data)
        except Exception as e:
            print(f"[WARN] can_hard_delete_user_document error: {e}")

    deleted_files = []
    if can_delete:
        if admin_client and storage_path:
            try:
                b_name, b_key = parse_storage_path(storage_path)
                admin_client.storage.from_(b_name).remove([b_key])
            except Exception as e:
                print(f"[WARN] Error removing storage object {storage_path}: {e}")

        if admin_client:
            try:
                admin_client.table("user_documents").delete().eq("id", doc_id).execute()
            except Exception as e:
                print(f"[WARN] Error deleting user_documents record: {e}")

        if APP_ENVIRONMENT != "production":
            db = SessionLocal()
            try:
                db.query(UserDocument).filter(UserDocument.id == doc_id).delete()
                db.commit()
            finally:
                db.close()
    else:
        # Soft-delete para retención y auditoría legal
        if admin_client:
            try:
                admin_client.table("user_documents").update({"is_active": False}).eq("id", doc_id).execute()
            except Exception as e:
                print(f"[WARN] Error deactivating user_document: {e}")

        if APP_ENVIRONMENT != "production":
            db = SessionLocal()
            try:
                db.query(UserDocument).filter(UserDocument.id == doc_id).update({"is_active": False})
                db.commit()
            finally:
                db.close()

    # Limpiar caché local del usuario
    user_cache = os.path.join(INPUT_DIR, user_id, filename)
    user_uuid_cache = os.path.join(INPUT_DIR, user_id, f"{doc_id}.pdf")
    for cp in (user_cache, user_uuid_cache):
        if os.path.exists(cp):
            try:
                os.remove(cp)
                deleted_files.append(os.path.basename(cp))
            except Exception as e:
                print(f"[WARN] Error removing user cache: {e}")

    # Limpiar mapeo si existe
    map_code = doc.get("template_code") or template_id
    for mp in [
        os.path.join(DATA_DIR, f"{user_id}_{map_code}_mapping.json"),
        os.path.join(DATA_DIR, f"{user_id}_{doc_id}_mapping.json"),
        os.path.join(DATA_DIR, f"{user_id}_{template_id}_mapping.json"),
        os.path.join(DATA_DIR, f"{map_code}_mapping.json"),
        os.path.join(DATA_DIR, f"{template_id}_mapping.json")
    ]:
        if os.path.exists(mp):
            try:
                os.remove(mp)
                deleted_files.append(os.path.basename(mp))
            except Exception:
                pass

    return {
        "status": "success",
        "message": f"Plantilla '{template_id}' eliminada exitosamente",
        "deleted": deleted_files or [filename]
    }

@app.get("/api/pdf/{template_id}/pages")
def get_pdf_pages(
    template_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = str(user["id"])
    company_id = str(user.get("company_id") or "local_company")
    is_admin = user.get("role") == "admin"

    doc = resolve_user_document(user_id, template_id, is_admin=is_admin, company_id=company_id)
    pdf_bytes = get_user_pdf_bytes(user_id, doc)

    processor = VisualPDFProcessor(output_dir=OUTPUT_DIR, dpi=120)
    pages = processor.render_all_pages_from_bytes(pdf_bytes, dpi=120)

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
def save_mapping(
    mapping: TemplateMapping,
    user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = str(user["id"])
    company_id = str(user.get("company_id") or "local_company")
    is_admin = user.get("role") == "admin"

    # Enforce document ownership: raises 403 if document belongs to another user
    doc = resolve_user_document(user_id, mapping.template_id, is_admin=is_admin, company_id=company_id)
    doc_id = str(doc.get("id")) if doc else None
    template_code = doc.get("template_code") if doc else None

    # Paths to persist user-isolated mapping
    paths_to_write = {
        os.path.join(DATA_DIR, f"{user_id}_{mapping.template_id}_mapping.json")
    }
    if template_code:
        paths_to_write.add(os.path.join(DATA_DIR, f"{user_id}_{template_code}_mapping.json"))
    if doc_id:
        paths_to_write.add(os.path.join(DATA_DIR, f"{user_id}_{doc_id}_mapping.json"))

    content_json = mapping.model_dump_json(indent=2)
    for p in paths_to_write:
        with open(p, "w", encoding="utf-8") as f:
            f.write(content_json)

    # Keep legacy format for backward compatibility
    legacy_paths = {
        os.path.join(DATA_DIR, f"{mapping.template_id}_mapping.json")
    }
    if template_code:
        legacy_paths.add(os.path.join(DATA_DIR, f"{template_code}_mapping.json"))
    if doc_id:
        legacy_paths.add(os.path.join(DATA_DIR, f"{doc_id}_mapping.json"))

    for lp in legacy_paths:
        try:
            with open(lp, "w", encoding="utf-8") as f:
                f.write(content_json)
        except Exception:
            pass
    return {"status": "success", "message": "Mapping saved successfully"}

@app.get("/api/mapping/{template_id}")
def get_mapping(
    template_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    user_id = str(user["id"])
    company_id = str(user.get("company_id") or "local_company")
    is_admin = user.get("role") == "admin"

    # Enforce document ownership: raises 403 if document belongs to another user
    doc = resolve_user_document(user_id, template_id, is_admin=is_admin, company_id=company_id)
    doc_id = str(doc.get("id")) if doc else None
    template_code = doc.get("template_code") if doc else None

    user_candidates = [
        os.path.join(DATA_DIR, f"{user_id}_{template_id}_mapping.json")
    ]
    if template_code:
        user_candidates.append(os.path.join(DATA_DIR, f"{user_id}_{template_code}_mapping.json"))
    if doc_id:
        user_candidates.append(os.path.join(DATA_DIR, f"{user_id}_{doc_id}_mapping.json"))

    # If ANY user-specific mapping file exists, load it directly and NEVER fall back to legacy!
    for u_path in user_candidates:
        if os.path.exists(u_path):
            with open(u_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)

    # Only if NO user-specific mapping exists at all, check legacy paths
    legacy_candidates = [
        os.path.join(DATA_DIR, f"{template_id}_mapping.json")
    ]
    if template_code:
        legacy_candidates.append(os.path.join(DATA_DIR, f"{template_code}_mapping.json"))
    if doc_id:
        legacy_candidates.append(os.path.join(DATA_DIR, f"{doc_id}_mapping.json"))

    for l_path in legacy_candidates:
        if os.path.exists(l_path):
            with open(l_path, "r", encoding="utf-8-sig") as f:
                return json.load(f)

    return {"template_id": template_id, "page_width": 0, "page_height": 0, "mappings": []}

def load_company_data_for_generation(supabase_user: Optional[Dict[str, Any]], user_client: Optional[Any]) -> Dict[str, Any]:
    """
    Carga la información corporativa para la generación del formulario.
    En producción: EXIGE consulta autoritativa a Supabase bajo RLS y prohíbe el uso de company_data.json.
    En local/staging: Intenta consulta a Supabase si hay sesión y recurre a company_data.json como fallback.
    """
    company_id = (supabase_user or {}).get("app_metadata", {}).get("company_id")
    
    if APP_ENVIRONMENT == "production":
        if not supabase_user or not user_client:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Se requiere sesión activa y válida en entorno productivo."
            )
        if not company_id:
            raise HTTPException(status_code=403, detail="Usuario carece de company_id en app_metadata.")

    if user_client and company_id:
        try:
            comp_res = user_client.table("companies").select("*").eq("id", company_id).single().execute()
            if comp_res.data:
                c_row = comp_res.data
                leg_res = user_client.table("legal_representatives").select("*").eq("company_id", company_id).eq("es_principal", True).execute()
                l_row = leg_res.data[0] if (leg_res.data and len(leg_res.data) > 0) else {}
                bank_res = user_client.table("company_bank_accounts").select("*").eq("company_id", company_id).eq("es_principal", True).execute()
                b_row = bank_res.data[0] if (bank_res.data and len(bank_res.data) > 0) else {}

                nit_val = str(c_row.get("nit", ""))
                dv_val = str(c_row.get("dv", "")) if c_row.get("dv") is not None else ""
                nit_formatted = f"{nit_val}-{dv_val}" if dv_val else nit_val

                return {
                    "razon_social": c_row.get("razon_social", ""),
                    "nombre_comercial": c_row.get("nombre_comercial", ""),
                    "nit": nit_formatted,
                    "nit_digits": nit_val,
                    "dv": dv_val,
                    "ciudad": c_row.get("ciudad", ""),
                    "departamento": c_row.get("departamento", ""),
                    "pais": c_row.get("pais", "Colombia"),
                    "direccion_principal": c_row.get("direccion_principal", ""),
                    "telefono": c_row.get("telefono") or c_row.get("telefono_fijo", ""),
                    "pagina_web": c_row.get("pagina_web", ""),
                    "correo_institucional": c_row.get("email_contacto") or c_row.get("pagina_web", ""),
                    "total_activos": str(c_row.get("total_activos") or ""),
                    "total_pasivos": str(c_row.get("total_pasivos") or ""),
                    "total_patrimonio": str(c_row.get("total_patrimonio") or ""),
                    "total_ingresos_mensuales": str(c_row.get("total_ingresos_mensuales") or ""),
                    "total_egresos_mensuales": str(c_row.get("total_egresos_mensuales") or ""),
                    "representante_legal": l_row.get("nombre_completo", ""),
                    "representante_nombre": l_row.get("nombres", ""),
                    "representante_apellido": l_row.get("apellidos", ""),
                    "correo_rep": l_row.get("email", ""),
                    "celular_rep": l_row.get("celular", ""),
                    "numero_cedula": l_row.get("numero_documento", ""),
                    "tipo_documento": l_row.get("tipo_documento", "C.C"),
                    "lugar_expedicion_rep": l_row.get("lugar_expedicion", ""),
                    "fecha_expedicion": l_row.get("fecha_expedicion", ""),
                    "fecha_expedicion_rep": l_row.get("fecha_expedicion", ""),
                    "entidad_bancaria": b_row.get("entidad_bancaria", "BANCOLOMBIA"),
                    "tipo_cuenta": b_row.get("tipo_cuenta", "Ahorros"),
                    "numero_cuenta": b_row.get("numero_cuenta", "00300833888"),
                    "firma_global": "global_signature.png"
                }
            elif APP_ENVIRONMENT == "production":
                raise HTTPException(status_code=404, detail="Empresa no encontrada en Supabase.")
            c_row = comp_res.data
            leg_res = (
                user_client
                .table("legal_representatives")
                .select("*")
                .eq("company_id", company_id)
                .eq("es_principal", True)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            l_row = leg_res.data[0] if (leg_res.data and len(leg_res.data) > 0) else {}
            return {
                "razon_social": c_row.get("razon_social", ""),
                "nit": f"{c_row.get('nit', '')}-{c_row.get('dv', '')}" if c_row.get("dv") else c_row.get("nit", ""),
                "ciudad": c_row.get("ciudad", ""),
                "departamento": c_row.get("departamento", ""),
                "pais": c_row.get("pais", "Colombia"),
                "direccion_principal": c_row.get("direccion_principal", ""),
                "telefono": c_row.get("telefono_fijo", ""),
                "correo_institucional": c_row.get("email_contacto", ""),
                "representante_legal": l_row.get("nombre_completo", ""),
                "correo_rep": l_row.get("email", ""),
                "celular_rep": l_row.get("celular", ""),
                "numero_cedula": l_row.get("numero_documento", ""),
                "tipo_documento": l_row.get("tipo_documento", "C.C"),
                "lugar_expedicion_rep": l_row.get("lugar_expedicion", ""),
                "fecha_expedicion": l_row.get("fecha_expedicion", "")
            }
        except HTTPException:
            raise
        except Exception as e:
            if APP_ENVIRONMENT == "production":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Servicio institucional de datos en Supabase no disponible: {str(e)}"
                )
            print(f"[WARN] Error loading company data from Supabase, falling back to local json: {e}")

    company_data_path = os.path.join(DATA_DIR, "company_data.json")
    if not os.path.exists(company_data_path):
        raise HTTPException(status_code=404, detail="Company data not found")
    with open(company_data_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

@app.post("/api/generate")
def generate_pdf(req: GenerateRequest, user: Dict[str, Any] = Depends(get_current_user)):
    token = user.get("token")
    supabase_user = user
    user_id = str(user["id"])
    company_id = str(user.get("company_id") or "local_company")
    user_client = user.get("user_client")
    is_admin = user.get("role") == "admin"

    admin_client = None
    try:
        admin_client = get_supabase_admin_client()
    except Exception as e:
        print(f"[WARN] generate_pdf admin_client error: {e}")

    target_version_id = req.template_version_id
    if not target_version_id and admin_client and company_id and company_id != "local_company":
        res_info = resolve_or_provision_template_version(
            template_code=req.template_id,
            filename=None,
            company_id=company_id,
            admin_client=admin_client,
            user_id=user_id
        )
        target_version_id = res_info.get("template_version_id")

    if APP_ENVIRONMENT == "production":
        if not target_version_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="En entorno de producción se exige template_version_id para registrar el ciclo de llenado."
            )

    # 0. Enforce conscious selection and resolve commercial profile (ADR-0008)
    resolved_cp = resolve_commercial_profile(req.commercial_profile_id, token=token)

    history_id = None
    user_client = None
    if token and supabase_user and target_version_id:
        try:
            user_client = get_supabase_user_client(token)
            comm_prof_id = None if req.commercial_profile_id in ("legal_rep_only", None, "null", "None") else req.commercial_profile_id
            start_res = user_client.rpc("start_form_fill", {
                "p_template_version_id": target_version_id,
                "p_commercial_profile_id": comm_prof_id,
                "p_metadata": {"is_temporary": req.is_temporary, "template_id": req.template_id}
            }).execute()
            history_id = start_res.data
        except Exception as e:
            if APP_ENVIRONMENT == "production":
                raise HTTPException(status_code=400, detail=f"Error al iniciar ciclo de llenado en Supabase: {str(e)}")
            print(f"[WARN] start_form_fill failed in {APP_ENVIRONMENT}: {e}")

    if APP_ENVIRONMENT == "production" and not history_id:
        raise HTTPException(status_code=500, detail="Fallo al registrar historial de llenado en Supabase.")

    # 1. Load company data (enforcing Supabase in production)
    company_data = load_company_data_for_generation(supabase_user, user_client)

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
    if req.mappings is not None:
        mappings = [m.model_dump() for m in req.mappings]
    else:
        doc = resolve_user_document(user_id, req.template_id, is_admin=is_admin, company_id=company_id)
        doc_id = str(doc.get("id")) if doc else None
        template_code = doc.get("template_code") if doc else None

        user_candidates = [
            os.path.join(DATA_DIR, f"{user_id}_{req.template_id}_mapping.json")
        ]
        if template_code:
            user_candidates.append(os.path.join(DATA_DIR, f"{user_id}_{template_code}_mapping.json"))
        if doc_id:
            user_candidates.append(os.path.join(DATA_DIR, f"{user_id}_{doc_id}_mapping.json"))

        found_path = None
        for u_path in user_candidates:
            if os.path.exists(u_path):
                found_path = u_path
                break

        if not found_path:
            legacy_candidates = [
                os.path.join(DATA_DIR, f"{req.template_id}_mapping.json")
            ]
            if template_code:
                legacy_candidates.append(os.path.join(DATA_DIR, f"{template_code}_mapping.json"))
            if doc_id:
                legacy_candidates.append(os.path.join(DATA_DIR, f"{doc_id}_mapping.json"))
            for l_path in legacy_candidates:
                if os.path.exists(l_path):
                    found_path = l_path
                    break

        if not found_path or not os.path.exists(found_path):
            raise HTTPException(status_code=404, detail=f"No mappings found for template {req.template_id}")

        with open(found_path, "r", encoding="utf-8-sig") as f:
            mapping_data = json.load(f)
            mappings = mapping_data.get("mappings", [])

    # 3. Locate input PDF (strictly owner-isolated)
    pdf_path = resolve_user_pdf_path(user_id, req.template_id, company_id=company_id)
    if not pdf_path or not os.path.exists(pdf_path):
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
            if custom_text is not None:
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

    if not placements and req.mappings is None and not mappings:
        raise HTTPException(status_code=400, detail="No matching fields or images to place onto PDF")

    user_out_dir = os.path.join(OUTPUT_DIR, user_id)
    os.makedirs(user_out_dir, exist_ok=True)
    out_filename = f"filled_{os.path.basename(pdf_path)}"
    out_path = os.path.join(user_out_dir, out_filename)
    processor = VisualPDFProcessor(output_dir=user_out_dir)
    processor.apply_visual_placements(pdf_path, placements, output_path=out_path)
    token_param = f"?token={token}" if token else ""
    download_url = f"/api/download/{out_filename}{token_param}"

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
def ai_fill_pdf(req: AiFillRequest, user: Dict[str, Any] = Depends(get_current_user)):
    token = user.get("token")
    supabase_user = user
    user_id = str(user["id"])
    company_id = str(user.get("company_id") or "local_company")
    user_client = user.get("user_client")

    # 0. Enforce conscious selection and resolve commercial profile (ADR-0008)
    resolved_cp = resolve_commercial_profile(req.commercial_profile_id, token=token)

    # 1. Locate input PDF (strictly owner-isolated)
    template_id = req.template_id
    pdf_path = resolve_user_pdf_path(user_id, template_id, company_id=company_id)
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail=f"Input PDF '{template_id}' not found")

    admin_client = None
    try:
        admin_client = get_supabase_admin_client()
    except Exception as e:
        print(f"[WARN] ai_fill admin_client error: {e}")

    target_version_id = req.template_version_id
    if not target_version_id and admin_client and company_id and company_id != "local_company":
        res_info = resolve_or_provision_template_version(
            template_code=req.template_id,
            filename=None,
            company_id=company_id,
            admin_client=admin_client,
            user_id=user_id
        )
        target_version_id = res_info.get("template_version_id")

    history_id = None
    if token and supabase_user and target_version_id:
        try:
            user_client = get_supabase_user_client(token)
            comm_prof_id = None if req.commercial_profile_id in ("legal_rep_only", None, "null", "None") else req.commercial_profile_id
            start_res = user_client.rpc("start_form_fill", {
                "p_template_version_id": target_version_id,
                "p_commercial_profile_id": comm_prof_id,
                "p_metadata": {"mode": "ai-fill", "template_id": req.template_id}
            }).execute()
            history_id = start_res.data
        except Exception as e:
            if APP_ENVIRONMENT == "production":
                raise HTTPException(status_code=400, detail=f"Error al iniciar ciclo de llenado en Supabase: {str(e)}")
            print(f"[WARN] start_form_fill failed in {APP_ENVIRONMENT}: {e}")

    if APP_ENVIRONMENT == "production" and not history_id:
        raise HTTPException(status_code=500, detail="Fallo al registrar historial de autollenado en Supabase.")

    # 2. Load company data (enforcing Supabase in production)
    company_data = load_company_data_for_generation(supabase_user, user_client)

    instructions = (
        "Por favor llena este formulario PDF con los datos principales de la empresa:\n"
        f"{json.dumps(company_data, ensure_ascii=False, indent=2)}\n\n"
        "Incluye datos de identificación (NIT, Razón Social, Representante Legal, Cédula), "
        "datos de contacto (Ciudad, Dirección, Correo, Celular, Teléfono) y "
        "datos bancarios (Banco, Tipo de cuenta, Número de cuenta) en los campos correspondientes."
    )

    try:
        from backend.pdf_filling_agent.agent import PDFAgent
        user_out_dir = os.path.join(OUTPUT_DIR, user_id)
        os.makedirs(user_out_dir, exist_ok=True)
        agent = PDFAgent(company_profile=company_data, commercial_profile=resolved_cp)
        output_path = agent.fill_pdf(pdf_path, instructions, output_dir=user_out_dir, mode="auto")
        out_filename = os.path.basename(output_path)
        token_param = f"?token={token}" if token else ""
        download_url = f"/api/download/{out_filename}{token_param}"

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

@app.get("/api/download/{history_id}")
async def download_file_by_history_id(
    history_id: str,
    request: Request,
    token: Optional[str] = None
):
    """
    Endpoint seguro de descarga autenticada por history_id (ADR-0011 Sección 7).
    Valida pertenencia contra form_fill_history y genera signed URL efímera (TTL 600s).
    Aplica protección contra enumeración ciega retornando 404 de manera uniforme.
    """
    auth_token = token
    if not auth_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            auth_token = auth_header.split(" ", 1)[1]
        elif "admin_session" in request.cookies:
            auth_token = request.cookies.get("admin_session")

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere autenticación para descargar este archivo."
        )

    user = None
    try:
        user = decode_supabase_jwt(auth_token)
    except Exception:
        try:
            from backend.db.auth import verify_session_token
            user = verify_session_token(auth_token)
        except Exception:
            user = None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o token inválido."
        )

    import urllib.parse
    clean_history_id = urllib.parse.unquote(history_id).strip()

    auth_user_id = str(user.get("sub") or user.get("id") or "")
    email = (user.get("email") or "").lower()

    valid_user_ids = set()
    if auth_user_id:
        valid_user_ids.add(auth_user_id)

    db = SessionLocal()
    try:
        query = db.query(CommercialProfile).filter(CommercialProfile.is_active == True)
        matching_profiles = []
        if auth_user_id:
            matching_profiles.extend(query.filter(CommercialProfile.id == auth_user_id).all())
        if email:
            matching_profiles.extend(query.filter(CommercialProfile.email.ilike(email)).all())
        for prof in matching_profiles:
            valid_user_ids.add(str(prof.id))
    finally:
        db.close()

    is_valid_uuid = False
    try:
        uuid.UUID(str(clean_history_id))
        is_valid_uuid = True
    except Exception:
        pass

    admin_client = None
    try:
        admin_client = get_supabase_admin_client()
    except Exception:
        pass

    if admin_client:
        try:
            # 1. Comprobar form_fill_history
            hist_res = (
                admin_client.table("form_fill_history")
                .select("id,operator_user_id,output_storage_path,company_id")
                .eq("id", clean_history_id)
                .limit(1)
                .execute()
            )
            if hist_res.data and len(hist_res.data) > 0:
                hist = hist_res.data[0]
                if str(hist.get("operator_user_id")) not in valid_user_ids:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Acceso denegado: no tienes permisos para acceder a este archivo."
                    )
                storage_path = hist.get("output_storage_path")
                if storage_path:
                    b_name, b_key = parse_storage_path(storage_path)
                    signed = admin_client.storage.from_(b_name).create_signed_url(b_key, expires_in=600)
                    signed_url = signed.get("signedURL") or signed.get("signedUrl")
                    if signed_url:
                        return RedirectResponse(signed_url)

            # 2. Comprobar user_documents (si se pasó un document_id)
            doc_res = (
                admin_client.table("user_documents")
                .select("id,user_id,storage_path")
                .eq("id", clean_history_id)
                .limit(1)
                .execute()
            )
            if doc_res.data and len(doc_res.data) > 0:
                doc = doc_res.data[0]
                if str(doc.get("user_id")) not in valid_user_ids:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Acceso denegado: no tienes permisos para acceder a este documento."
                    )
                storage_path = doc.get("storage_path")
                if storage_path:
                    b_name, b_key = parse_storage_path(storage_path)
                    signed = admin_client.storage.from_(b_name).create_signed_url(b_key, expires_in=600)
                    signed_url = signed.get("signedURL") or signed.get("signedUrl")
                    if signed_url:
                        return RedirectResponse(signed_url)
        except HTTPException:
            raise
        except Exception as e:
            print(f"[WARN] Error fetching form_fill_history {clean_history_id}: {e}")

    # Fallback local para desarrollo y tests
    if APP_ENVIRONMENT != "production":
        # 3. Comprobar UserDocument local en SQLite
        db = SessionLocal()
        try:
            local_doc = db.query(UserDocument).filter(
                (UserDocument.id == clean_history_id) | (UserDocument.filename == clean_history_id)
            ).first()
            if local_doc:
                if str(local_doc.user_id) not in valid_user_ids:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Acceso denegado: no tienes permisos para acceder a este documento."
                    )
                for uid in valid_user_ids:
                    for candidate_name in [local_doc.filename, f"{local_doc.id}.pdf", f"{clean_history_id}.pdf", clean_history_id]:
                        local_cache = os.path.join(INPUT_DIR, uid, candidate_name)
                        if os.path.exists(local_cache) and os.path.isfile(local_cache):
                            return FileResponse(path=local_cache, filename=local_doc.filename, media_type="application/pdf")
        finally:
            db.close()

        search_names = [clean_history_id]
        if not clean_history_id.lower().endswith(".pdf"):
            search_names.append(f"{clean_history_id}.pdf")
        else:
            search_names.append(clean_history_id[:-4])

        # 4. Comprobar directorio de salida aislado del usuario para todos sus IDs válidos
        for uid in valid_user_ids:
            for c_name in search_names:
                candidate = os.path.join(OUTPUT_DIR, uid, c_name)
                if os.path.exists(candidate) and os.path.isfile(candidate):
                    download_name = os.path.basename(candidate)
                    if not download_name.lower().endswith(".pdf"):
                        download_name = f"{download_name}.pdf"
                    return FileResponse(
                        path=candidate,
                        filename=download_name,
                        media_type="application/pdf"
                    )

        # 5. Comprobar si el archivo solicitado existe en la carpeta de OTRO usuario (aislamiento estricto)
        if os.path.exists(OUTPUT_DIR):
            for entry in os.listdir(OUTPUT_DIR):
                other_dir = os.path.join(OUTPUT_DIR, entry)
                if os.path.isdir(other_dir) and entry not in valid_user_ids:
                    for c_name in search_names:
                        if os.path.exists(os.path.join(other_dir, c_name)):
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Acceso denegado: el archivo pertenece a otro usuario."
                            )

        if os.path.exists(INPUT_DIR):
            for entry in os.listdir(INPUT_DIR):
                other_dir = os.path.join(INPUT_DIR, entry)
                if os.path.isdir(other_dir) and entry not in valid_user_ids:
                    for c_name in search_names:
                        if os.path.exists(os.path.join(other_dir, c_name)):
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Acceso denegado: el documento pertenece a otro usuario."
                            )

        # 6. Fallback legacy local (archivos no particionados generados en tests)
        for c_name in search_names:
            candidate = os.path.join(OUTPUT_DIR, c_name)
            if os.path.exists(candidate) and os.path.isfile(candidate):
                download_name = os.path.basename(candidate)
                if not download_name.lower().endswith(".pdf"):
                    download_name = f"{download_name}.pdf"
                return FileResponse(
                    path=candidate,
                    filename=download_name,
                    media_type="application/pdf"
                )

    if is_valid_uuid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado o documento no autorizado."
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Archivo no encontrado o acceso no autorizado."
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
