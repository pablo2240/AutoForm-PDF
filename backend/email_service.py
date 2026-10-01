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

def get_smtp_config():
    app_env = os.getenv("APP_ENVIRONMENT", os.getenv("ENVIRONMENT", "local")).lower()
    return {
        "app_env": app_env,
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
        "from_email": os.getenv("SMTP_FROM_EMAIL", "").strip() or os.getenv("SMTP_USER", "").strip() or "autoform.soporte@gmail.com",
        "from_name": os.getenv("SMTP_FROM_NAME", "AutoForm PDF - Seguridad").strip(),
        "site_url": os.getenv("SITE_URL", "http://localhost:5173").rstrip("/")
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
    .btn-reset {{
      display: inline-block;
      background-color: #2563eb;
      color: #ffffff !important;
      text-decoration: none;
      font-weight: 600;
      font-size: 15px;
      padding: 14px 32px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
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

      <div class="button-container">
        <a href="{reset_link}" class="btn-reset" target="_blank" rel="noopener noreferrer">
          Restablecer Contraseña
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

    # Development simulation fallback
    if not cfg["user"] or not cfg["password"]:
        if cfg["app_env"] in ("local", "test", "testing", "development"):
            print("\n" + "=" * 70, flush=True)
            print("[DEV EMAIL SIMULATION] Credenciales SMTP no configuradas. Simulación de envío:", flush=True)
            print(f"[DEV EMAIL SIMULATION] Destinatario: {clean_recipient} ({recipient_name})", flush=True)
            print(f"[DEV EMAIL SIMULATION] Enlace de Restablecimiento: {reset_link}", flush=True)
            print("=" * 70 + "\n", flush=True)
            return True
        else:
            raise RuntimeError(
                "SMTP_USER y SMTP_PASSWORD son obligatorios en entorno de producción/staging para enviar correos."
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
        print(f"[SMTP_ERROR] Error al despachar correo a {clean_recipient}: {str(e)}", flush=True)
        raise e
