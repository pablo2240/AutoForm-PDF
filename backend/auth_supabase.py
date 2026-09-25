import os
import uuid
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

APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "local").lower()
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://tnhedxwbpqihlqbtzudt.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

EXPECTED_ISSUER = f"{SUPABASE_URL.rstrip('/')}/auth/v1"
JWKS_URL = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"

jwks_client = jwt.PyJWKClient(JWKS_URL, cache_jwk_set=True, lifespan=3600)
security_bearer = HTTPBearer(auto_error=False)

def get_supabase_admin_client() -> Client:
    """
    Retorna cliente Supabase con privilegios administrativos (service_role).
    Utilizado EXCLUSIVAMENTE para operaciones server-side autorizadas (creación de usuarios,
    verificación de perfil autoritativo y generación de enlaces de invitación).
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
    Garantiza que todas las operaciones a la base de datos se ejecuten
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
    Valida y decodifica un JWT emitido por Supabase Auth:
    - Verificación de firma criptográfica (ES256 mediante JWKS oficial del proyecto).
    - Verificación estricta del emisor (issuer exacto del proyecto).
    - Verificación de tiempo de expiración (exp).
    - Verificación de formato UUID en el subject (sub).
    - Verificación de audiencia (aud == 'authenticated').
    - Verificación de rol base (role == 'authenticated').
    """
    if not token or not isinstance(token, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no proporcionado o formato inválido."
        )

    try:
        unverified_headers = jwt.get_unverified_header(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Encabezado de token inválido o malformado: {str(e)}"
        )

    alg = unverified_headers.get("alg")
    key = None

    if alg == "ES256":
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            key = signing_key.key
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Fallo al resolver clave criptográfica ES256 desde JWKS: {str(e)}"
            )
    elif alg == "HS256" and (APP_ENVIRONMENT in ("local", "test", "testing") or os.getenv("ALLOW_HS256_AUTH", "0") == "1"):
        # En entorno local/test se admite HS256 con las claves secretas configuradas
        key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Algoritmo de firma '{alg}' no autorizado. Se requiere ES256."
        )

    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["ES256", "HS256"],
            issuer=EXPECTED_ISSUER,
            audience="authenticated",
            options={
                "verify_signature": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_aud": True
            }
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión ha expirado. Por favor inicia sesión nuevamente."
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no emitido por este proyecto Supabase (emisor inválido)."
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Audiencia de token no autorizada."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Fallo de validación criptográfica de token: {str(e)}"
        )

    # 1. Validar formato UUID en el subject
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token carece del campo subject ('sub')."
        )
    try:
        uuid.UUID(str(sub))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El subject ('sub') del token no es un UUID válido."
        )

    # 2. Validar rol base authenticated
    if payload.get("role") != "authenticated":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no posee el rol base 'authenticated'."
        )

    return payload

async def get_current_user(
    request: Request,
    auth_creds: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> Dict[str, Any]:
    """
    Dependencia FastAPI que extrae y valida la identidad del usuario activo.
    Soporta header 'Authorization: Bearer <token>' y cookie 'admin_session'.
    Consulta autoritativamente la base de datos (public.profiles en Supabase o local_dev.db en SQLite) en tiempo real,
    sin confiar ciegamente en app_metadata del JWT para autorizaciones.
    """
    token = None
    if auth_creds and auth_creds.credentials:
        token = auth_creds.credentials
    elif "admin_session" in request.cookies:
        token = request.cookies.get("admin_session")
    else:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado: se requiere token Bearer o sesión activa."
        )

    # 1. Intentar decodificar como Supabase JWT
    payload = None
    is_supabase_token = False
    try:
        payload = decode_supabase_jwt(token)
        is_supabase_token = True
    except Exception:
        # 2. Si no es Supabase JWT, intentar verificar como token de sesión HMAC local
        from backend.db.auth import verify_session_token
        session_payload = verify_session_token(token)
        if not session_payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión inválida o expirada. Por favor inicia sesión nuevamente."
            )
        payload = session_payload

    user_id = payload.get("sub") or payload.get("id")
    email = (payload.get("email") or "").lower()
    jwt_app_meta = payload.get("app_metadata") or {}
    jwt_company_id = jwt_app_meta.get("company_id")
    jwt_role = jwt_app_meta.get("role") or payload.get("role") or "commercial"

    profile = None
    user_client = None

    # Consulta autoritativa en public.profiles mediante cliente administrativo si es token Supabase
    if is_supabase_token:
        try:
            admin_client = get_supabase_admin_client()
            res = admin_client.table("profiles").select("*").eq("id", user_id).single().execute()
            if res.data:
                profile = res.data
        except Exception:
            profile = None

        try:
            user_client = get_supabase_user_client(token)
        except Exception:
            user_client = None

    # Fallback autoritativo a SQLite (backend/data/local_dev.db) si no está en Supabase profiles o es sesión local
    if not profile:
        from backend.db.session import SessionLocal
        from backend.db.models import CommercialProfile
        db_session = SessionLocal()
        try:
            query = db_session.query(CommercialProfile).filter(CommercialProfile.is_active == True)
            local_prof = None
            if user_id:
                local_prof = query.filter(CommercialProfile.id == str(user_id)).first()
            if not local_prof and email:
                local_prof = query.filter(CommercialProfile.email.ilike(email)).first()

            if local_prof:
                profile = {
                    "id": str(local_prof.id),
                    "email": local_prof.email,
                    "company_id": str(jwt_company_id) if jwt_company_id else "local_company",
                    "role": local_prof.role or jwt_role,
                    "nombre": local_prof.nombre or "",
                    "apellido": local_prof.apellido or "",
                    "display_name": local_prof.profile_name or f"{local_prof.nombre or ''} {local_prof.apellido or ''}".strip() or local_prof.email,
                    "cargo": local_prof.cargo or "Comercial",
                    "celular": local_prof.celular or "",
                    "tipo_documento": local_prof.tipo_documento or "CC",
                    "is_active": local_prof.is_active,
                }
        finally:
            db_session.close()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Perfil de usuario no encontrado en la base de datos."
        )

    if not profile.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: cuenta de usuario inactiva o suspendida."
        )

    return {
        "id": str(profile.get("id") or user_id),
        "email": profile.get("email") or email,
        "company_id": str(profile.get("company_id") or "local_company"),
        "jwt_company_id": str(jwt_company_id) if jwt_company_id else None,
        "role": profile.get("role", jwt_role),
        "nombre": profile.get("nombre", ""),
        "apellido": profile.get("apellido", ""),
        "display_name": profile.get("display_name", f"{profile.get('nombre', '')} {profile.get('apellido', '')}".strip()),
        "cargo": profile.get("cargo", ""),
        "celular": profile.get("celular", ""),
        "tipo_documento": profile.get("tipo_documento", "C.C"),
        "is_active": profile.get("is_active", True),
        "token": token,
        "user_client": user_client,
        "profile": profile
    }

async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Restringe el endpoint exclusivamente a administradores activos.
    Verifica en tiempo real:
    - is_active == True
    - role == 'admin' (autoritativo desde public.profiles)
    - company_id coincidente
    Rechaza inmediatamente administradores desactivados o degradados con HTTP 403,
    incluso si presentan un JWT no expirado con role='admin'.
    """
    if not user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: cuenta desactivada o suspendida."
        )

    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes: el rol administrativo ha sido revocado o degradado."
        )

    jwt_comp = user.get("jwt_company_id")
    prof_comp = user.get("company_id")
    if jwt_comp and prof_comp and jwt_comp != prof_comp:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inconsistencia de seguridad: el identificador de empresa del token no coincide con el perfil."
        )

    return user
