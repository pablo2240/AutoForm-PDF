import os
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


PRODUCTION_SUPABASE_REF = os.getenv("SUPABASE_PRODUCTION_REF", "tnhedxwbpqihlqbtzudt")
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _guard_production_writes(original):
    def guarded(self, request, *args, **kwargs):
        if PRODUCTION_SUPABASE_REF in str(request.url.host) and request.method.upper() in _WRITE_METHODS:
            raise RuntimeError(
                f"ESCRITURA EN PRODUCCIÓN PROHIBIDA: {request.method} {request.url.host}{request.url.path}. "
                "Las pruebas destructivas solo pueden usar staging o mocks (ver tests/test_e2e_supabase_controlled.py)."
            )
        return original(self, request, *args, **kwargs)
    return guarded


@pytest.fixture(autouse=True)
def prevent_production_supabase_writes(monkeypatch):
    """Las pruebas automáticas jamás crean/borran usuarios ni filas en el proyecto Supabase de producción."""
    monkeypatch.setattr(httpx.Client, "send", _guard_production_writes(httpx.Client.send))
    monkeypatch.setattr(httpx.AsyncClient, "send", _guard_production_writes(httpx.AsyncClient.send))


@pytest.fixture(autouse=True)
def isolate_local_state(tmp_path, monkeypatch, request):
    """Las pruebas trabajan sobre copias temporales de backend/data, input/, output/ y de la base local.

    Evita que los tests dejen perfiles `test_*`, mapeos o PDFs en el repositorio (y que de ahí
    lleguen a producción) y que escriban en la base real (SQLite local o Neon).
    """
    import importlib
    import shutil
    try:
        main = importlib.import_module("backend.main")
    except Exception:
        yield
        return

    data_dir = tmp_path / "data"
    shutil.copytree(main.DATA_DIR, data_dir, ignore=shutil.ignore_patterns("*.db", "storage_pre_migration_backup", "__pycache__", "reference_library"))
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    redirected = {
        "DATA_DIR": str(data_dir), "SIGNATURES_DIR": str(data_dir / "signatures"),
        "ACTIVE_SLOT_FILE": str(data_dir / "active_slot.json"),
        "INPUT_DIR": str(tmp_path / "input"), "OUTPUT_DIR": str(tmp_path / "output"),
    }
    for name, value in redirected.items():
        monkeypatch.setattr(main, name, value)
        # tests that did `from backend.main import DATA_DIR` hold their own copy of the real path
        if hasattr(request.module, name):
            monkeypatch.setattr(request.module, name, value)

    from sqlalchemy import create_engine
    from backend.db import session as db_session
    from backend.db.models import Base
    test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    if db_session.engine.url.get_backend_name() == "sqlite" and db_session.engine.url.database and os.path.exists(db_session.engine.url.database):
        test_engine.dispose()
        shutil.copy(db_session.engine.url.database, tmp_path / "test.db")
        test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    original_bind = db_session.SessionLocal.kw.get("bind")
    db_session.SessionLocal.configure(bind=test_engine)
    yield
    db_session.SessionLocal.configure(bind=original_bind)
    test_engine.dispose()
