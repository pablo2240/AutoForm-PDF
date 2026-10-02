import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Explicit path resolution per AGENTS.md rule
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ENV_PATH = ROOT_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    load_dotenv(override=True)

def mask_email(email: str) -> str:
    """Enmascara correo para logs seguros sin exponer PII (ej: p***s@iaclatam.com)."""
    if not email or "@" not in email:
        return ""
    parts = email.split("@", 1)
    name = parts[0]
    domain = parts[1]
    if len(name) <= 2:
        masked_name = name[0] + "*"
    else:
        masked_name = name[0] + ("*" * (len(name) - 2)) + name[-1]
    return f"{masked_name}@{domain}"

def get_missing_smtp_vars() -> list:
    """
    Verifica la presencia explícita de las 6 variables requeridas para SMTP corporativo:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL, SMTP_FROM_NAME.
    """
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM_EMAIL", "SMTP_FROM_NAME"]
    missing = []
    for var in required:
        val = os.getenv(var, "").strip()
        if not val:
            missing.append(var)
    if "SMTP_PORT" not in missing:
        try:
            int(os.getenv("SMTP_PORT", "587").strip())
        except ValueError:
            missing.append("SMTP_PORT (puerto numérico inválido)")
    return missing

def get_smtp_config():
    app_env = os.getenv("APP_ENVIRONMENT", os.getenv("ENVIRONMENT", "local")).lower()
    raw_port = os.getenv("SMTP_PORT", "").strip()
    try:
        port = int(raw_port) if raw_port else 587
    except ValueError:
        port = 587

    site_url = os.getenv("SITE_URL", "").strip().rstrip("/")
    if not site_url:
        if app_env in ("production", "staging"):
            site_url = "https://autoform-pdf-web.onrender.com"
        else:
            site_url = "http://localhost:5173"

    user = os.getenv("SMTP_USER", "").strip()
    return {
        "app_env": app_env,
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": port,
        "raw_port": raw_port,
        "user": user,
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
        "from_email": os.getenv("SMTP_FROM_EMAIL", "").strip() or user,
        "from_name": os.getenv("SMTP_FROM_NAME", "").strip() or "AutoForm PDF - Seguridad",
        "site_url": site_url
    }

def render_reset_email_html(recipient_name: str, reset_link: str) -> str:
    """Generates an executive, responsive corporate HTML template for password reset."""
    display_name = recipient_name.strip() if recipient_name and recipient_name.strip() else "Usuario Comercial"
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Restablecer Contraseña - AutoForm PDF</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #f8fafc;
      color: #1e293b;
      margin: 0;
      padding: 0;
      -webkit-font-smoothing: antialiased;
    }}
    .email-container {{
      max-width: 580px;
      margin: 40px auto;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }}
    .email-header {{
      background: #0f172a;
      padding: 32px 36px;
      text-align: left;
      border-bottom: 3px solid #3b82f6;
    }}
    .brand-title {{
      color: #ffffff;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.5px;
      margin: 0;
    }}
    .brand-subtitle {{
      color: #94a3b8;
      font-size: 13px;
      margin: 4px 0 0 0;
    }}
    .email-body {{
      padding: 36px 36px 28px 36px;
      line-height: 1.6;
    }}
    .greeting {{
      font-size: 17px;
      font-weight: 600;
      color: #0f172a;
      margin-top: 0;
      margin-bottom: 16px;
    }}
    .message-text {{
      font-size: 15px;
      color: #334155;
      margin-bottom: 24px;
    }}
    .button-container {{
      text-align: center;
      margin: 32px 0;
    }}
    .btn-reset, a.btn-reset, a.btn-reset:visited, a.btn-reset:hover, a.btn-reset:active {{
      display: inline-block;
      background-color: #2563eb;
      color: #ffffff !important;
      text-decoration: none !important;
      font-weight: 600;
      font-size: 15px;
      padding: 14px 32px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
    }}
    .btn-reset span {{
      color: #ffffff !important;
      text-decoration: none !important;
    }}
    .alert-box {{
      background-color: #f0fdf4;
      border-left: 4px solid #16a34a;
      padding: 14px 16px;
      margin: 24px 0;
      border-radius: 4px;
    }}
    .alert-box p {{
      margin: 0;
      font-size: 13px;
      color: #166534;
      line-height: 1.5;
    }}
    .raw-link-box {{
      background-color: #f1f5f9;
      padding: 12px 16px;
      border-radius: 6px;
      font-family: monospace;
      font-size: 12px;
      word-break: break-all;
      color: #475569;
      margin-top: 16px;
    }}
    .email-footer {{
      background-color: #f8fafc;
      padding: 24px 36px;
      border-top: 1px solid #e2e8f0;
      text-align: center;
      font-size: 12px;
      color: #64748b;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="email-container">
    <div class="email-header">
      <h1 class="brand-title">AutoForm PDF</h1>
      <p class="brand-subtitle">Ingeniería Asistida Por Computador S.A.S. (IAC Latam)</p>
    </div>
    
    <div class="email-body">
      <p class="greeting">Hola, {display_name}</p>
      
      <p class="message-text">
        Hemos recibido una solicitud para restablecer la contraseña de tu cuenta de acceso a la plataforma comercial <strong>AutoForm PDF</strong>.
      </p>

      <div class="button-container" style="text-align: center; margin: 32px 0;">
        <a href="{reset_link}" class="btn-reset" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #2563eb; color: #ffffff !important; text-decoration: none !important; font-weight: 600; font-size: 15px; padding: 14px 32px; border-radius: 8px; box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);">
          <span style="color: #ffffff !important; text-decoration: none !important; font-weight: 600; font-size: 15px;">Restablecer Contraseña</span>
        </a>
      </div>

      <div class="alert-box">
        <p><strong>Seguridad y vigencia:</strong> Este enlace es de <strong>un solo uso</strong> y caducará automáticamente en <strong>15 minutos</strong>. Una vez utilizado, quedará invalidado de forma permanente.</p>
      </div>

      <p class="message-text" style="font-size: 13px; color: #64748b; margin-top: 20px;">
        Si el botón superior no funciona, copia y pega la siguiente dirección en tu navegador:
      </p>
      <div class="raw-link-box">
        {reset_link}
      </div>

      <p class="message-text" style="font-size: 13px; color: #64748b; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 16px;">
        Si no solicitaste este cambio, puedes ignorar este correo con total tranquilidad. Tu contraseña actual no ha sido modificada y tu cuenta permanece segura.
      </p>
    </div>

    <div class="email-footer">
      <p style="margin: 0 0 6px 0;"><strong>AutoForm PDF</strong> &bull; Sistema de Seguridad y Gestión de Identidades</p>
      <p style="margin: 0;">&copy; Ingeniería Asistida Por Computador S.A.S. Todos los derechos reservados.</p>
    </div>
  </div>
</body>
</html>"""

def send_password_reset_email(
    recipient_email: str,
    recipient_name: str,
    reset_link: str,
    timeout_seconds: float = 8.0
) -> bool:
    """
    Synchronously dispatches the password reset email via SMTP (e.g. Gmail App Password).
    In local development or test mode without SMTP credentials, logs the link to console.
    """
    cfg = get_smtp_config()
    clean_recipient = recipient_email.strip().lower()
    missing_vars = get_missing_smtp_vars()

    # Development simulation fallback when running locally without explicit SMTP config
    if missing_vars:
        if cfg["app_env"] in ("local", "development") and not os.getenv("STRICT_SMTP"):
            print("\n" + "=" * 70, flush=True)
            print(f"[DEV EMAIL SIMULATION] Faltan variables SMTP: {', '.join(missing_vars)}. Simulación de envío:", flush=True)
            print(f"[DEV EMAIL SIMULATION] Destinatario: {mask_email(clean_recipient)} ({recipient_name})", flush=True)
            print(f"[DEV EMAIL SIMULATION] Enlace de Restablecimiento: {reset_link}", flush=True)
            print("=" * 70 + "\n", flush=True)
            return True
        else:
            raise RuntimeError(
                f"Configuración SMTP incompleta en entorno {cfg['app_env']}. Faltan variables requeridas: {', '.join(missing_vars)}"
            )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Restablecer Contraseña - AutoForm PDF"
    msg["From"] = formataddr((cfg["from_name"], cfg["from_email"]))
    msg["To"] = clean_recipient

    plain_text = (
        f"Hola {recipient_name},\n\n"
        f"Hemos recibido una solicitud para restablecer tu contraseña en AutoForm PDF.\n"
        f"Accede al siguiente enlace para definir tu nueva contraseña (válido por 15 minutos):\n\n"
        f"{reset_link}\n\n"
        f"Si no solicitaste este cambio, puedes ignorar este mensaje.\n\n"
        f"AutoForm PDF - Ingeniería Asistida Por Computador S.A.S.\n"
    )

    html_content = render_reset_email_html(recipient_name, reset_link)

    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        if cfg["port"] == 465:
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=timeout_seconds) as server:
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_email"], [clean_recipient], msg.as_string())
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=timeout_seconds) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_email"], [clean_recipient], msg.as_string())
        return True
    except Exception as e:
        print(f"[SMTP_ERROR] Error al despachar correo a {mask_email(clean_recipient)}: {type(e).__name__}: {str(e)}", flush=True)
        raise e
