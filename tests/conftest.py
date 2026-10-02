import pytest
import httpx
import smtplib

@pytest.fixture(autouse=True)
def prevent_unmocked_external_email_calls(monkeypatch):
    """
    Guarda global estricta para asegurar que ninguna prueba automatizada
    realice llamadas de red reales a Microsoft Graph/Entra ID ni envíos SMTP.
    """
    original_post = httpx.Client.post

    def guarded_post(self, url, *args, **kwargs):
        url_str = str(url)
        if "login.microsoftonline.com" in url_str or "graph.microsoft.com" in url_str:
            raise RuntimeError(
                f"LLAMADA EXTERNA PROHIBIDA: Petición real a Microsoft Graph/Entra ({url_str}) sin mock en pruebas automatizadas."
            )
        return original_post(self, url, *args, **kwargs)

    def forbidden_smtp(*args, **kwargs):
        raise RuntimeError("LLAMADA EXTERNA PROHIBIDA: Conexión SMTP real sin mock en pruebas automatizadas.")

    monkeypatch.setattr(httpx.Client, "post", guarded_post)
    monkeypatch.setattr(smtplib, "SMTP", forbidden_smtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden_smtp)
