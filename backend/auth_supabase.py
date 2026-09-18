import os
from pathlib import Path
from typing import Optional, Dict, Any
import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, Security, Request, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions

# Explicit path resolution per AGENTS.md rule
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ENV_PATH = ROOT_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    load_dotenv(override=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://tnhedxwbpqihlqbtzudt.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

JWKS_URL = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
jwks_client = jwt.PyJWKClient(JWKS_URL, cache_jwk_set=True, lifespan=3600)

security_bearer = HTTPBearer(auto_error=False)

def get_supabase_admin_client() -> Client:
    """
    Retorna cliente Supabase con privilegios administrativos (service_role).
    Utilizado EXCLUSIVAMENTE para operaciones server-side seguras (creación de usuarios
    con app_metadata y generación de enlaces seguros de recuperación/activación).
    """
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_SERVICE_ROLE_KEY no está configurada en el servidor."
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def get_supabase_user_client(access_token: str) -> Client:
    """
    Retorna cliente Supabase inyectando el token JWT del usuario actual.
    Garantiza que todas las operaciones y consultas a la base de datos se ejecuten
    bajo las políticas de Row Level Security (RLS) del usuario autenticado.
    """
    if not SUPABASE_ANON_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_ANON_KEY no está configurada en el servidor."
        )
    options = SyncClientOptions(headers={"Authorization": f"Bearer {access_token}"})
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY, options=options)

def decode_supabase_jwt(token: str) -> Dict[str, Any]:
    """
    Valida y decodifica un JWT emitido por Supabase Auth utilizando verificación
    criptográfica asimétrica ES256 contra el endpoint oficial JWKS.
    """
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "HS256"],
            audience="authenticated"
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión ha expirado. Por favor inicia sesión nuevamente."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token de autorización inválido: {str(e)}"
        )

async def get_current_user(
    request: Request,
    auth_creds: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> Dict[str, Any]:
    """
    Dependencia FastAPI que extrae y valida la identidad del usuario activo.
    Soporta header 'Authorization: Bearer <token>' y cookie 'admin_session'.
    Verifica que el usuario pertenezca a una empresa activa y esté habilitado.
    """
    token = None
    if auth_creds and auth_creds.credentials:
        token = auth_creds.credentials
    elif "admin_session" in request.cookies:
        token = request.cookies.get("admin_session")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado: se requiere token Bearer o sesión activa."
        )

    payload = decode_supabase_jwt(token)
    user_id = payload.get("sub")
    email = (payload.get("email") or "").lower()
    app_meta = payload.get("app_metadata") or {}
    user_meta = payload.get("user_metadata") or {}
    
    company_id = app_meta.get("company_id")
    role = app_meta.get("role", "commercial")

    # Consultar perfil en Supabase usando el contexto del usuario (respeta RLS)
    user_client = get_supabase_user_client(token)
    try:
        res = user_client.table("profiles").select("*").eq("id", user_id).single().execute()
        profile = res.data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Error al consultar perfil del usuario o acceso denegado por RLS."
        )

    if not profile or not profile.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo, suspendido o perfil no encontrado."
        )

    return {
        "id": user_id,
        "email": email,
        "company_id": str(profile.get("company_id")),
        "role": profile.get("role", role),
        "nombre": profile.get("nombre", user_meta.get("nombre", "")),
        "apellido": profile.get("apellido", user_meta.get("apellido", "")),
        "display_name": profile.get("display_name", f"{profile.get('nombre', '')} {profile.get('apellido', '')}".strip()),
        "cargo": profile.get("cargo", user_meta.get("cargo", "")),
        "celular": profile.get("celular", user_meta.get("celular", "")),
        "tipo_documento": profile.get("tipo_documento", "C.C"),
        "is_active": profile.get("is_active", True),
        "token": token,
        "user_client": user_client
    }

async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Dependencia FastAPI que restringe el endpoint exclusivamente a administradores activos.
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes: esta acción requiere rol de Administrador."
        )
    return user
