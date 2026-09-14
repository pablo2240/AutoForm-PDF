import os
import secrets
import hashlib
import hmac
import time
from typing import Optional, Dict

SESSION_SECRET = os.getenv("SESSION_SECRET") or os.getenv("ADMIN_PASSWORD") or "iac_secret_signing_key_2026"
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
    sig = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
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
        expected_sig = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not secrets.compare_digest(sig, expected_sig):
            return None
        ts = int(ts_str)
        if time.time() - ts > max_age_seconds:
            return None
        return {"email": email, "role": role, "timestamp": ts_str}
    except Exception:
        return None
