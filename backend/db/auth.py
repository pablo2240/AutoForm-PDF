import os
import secrets
import hashlib
import hmac
import time
from typing import Optional, Dict

INSECURE_DEFAULT_SECRETS = {
    "iac_secret_signing_key_2026",
    "secret",
    "changeme",
    "admin",
    "password",
    "123456",
}

def resolve_session_secret(app_env: Optional[str] = None, raw_secret: Optional[str] = None) -> str:
    """
    Resolves and enforces SESSION_SECRET based on the execution environment.

    Rules:
    - In staging and production environments, SESSION_SECRET must be explicitly defined
      via environment variable. Fallback values are strictly forbidden.
    - If SESSION_SECRET in staging/production is empty or matches known insecure default/fallback
      values, startup fails immediately.
    - In local/development/test environments, if SESSION_SECRET is not set, a controlled
      local development signing key is used.
    """
    env = (app_env if app_env is not None else os.getenv("APP_ENVIRONMENT", os.getenv("ENVIRONMENT", "local"))).lower()
    val = raw_secret if raw_secret is not None else os.getenv("SESSION_SECRET")

    if env in ("production", "staging"):
        if not val or not val.strip():
            raise RuntimeError(
                f"SESSION_SECRET environment variable is required and must be set securely in {env} environment."
            )
        trimmed = val.strip()
        if trimmed in INSECURE_DEFAULT_SECRETS:
            raise RuntimeError(
                f"SESSION_SECRET in {env} environment cannot use a known or insecure default value."
            )
        if len(trimmed) < 32:
            raise RuntimeError(
                f"SESSION_SECRET in {env} environment must be at least 32 characters long for cryptographic security."
            )
        return trimmed
    else:
        if val and val.strip():
            return val.strip()
        admin_pass = os.getenv("ADMIN_PASSWORD")
        if admin_pass and admin_pass.strip():
            return admin_pass.strip()
        return "iac_secret_signing_key_2026"

SESSION_SECRET = resolve_session_secret()
SESSION_MAX_AGE_SECONDS = int(os.getenv("SESSION_MAX_AGE_SECONDS", str(86400 * 7))) # Default 7 days (604,800s)

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000)
    return f"{salt}:{key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    if not hashed or ":" not in hashed:
        return False
    try:
        salt, expected_key = hashed.split(":", 1)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000)
        return secrets.compare_digest(key.hex(), expected_key)
    except Exception:
        return False

def create_session_token(email: str, role: str) -> str:
    """Generates a tamper-proof signed session token (email:role:timestamp:signature)."""
    ts = str(int(time.time()))
    payload = f"{email}|{role}|{ts}"
    secret = resolve_session_secret()
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"

def verify_session_token(token: str, max_age_seconds: int = SESSION_MAX_AGE_SECONDS) -> Optional[Dict[str, str]]:
    """Verifies the session token signature and validity window (default 7 days)."""
    if not token or "|" not in token:
        return None
    try:
        parts = token.split("|")
        if len(parts) != 4:
            return None
        email, role, ts_str, sig = parts
        payload = f"{email}|{role}|{ts_str}"
        secret = resolve_session_secret()
        expected_sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(sig, expected_sig):
            return None
        ts = int(ts_str)
        if time.time() - ts > max_age_seconds:
            return None
        return {"email": email, "role": role, "timestamp": ts_str}
    except Exception:
        return None
