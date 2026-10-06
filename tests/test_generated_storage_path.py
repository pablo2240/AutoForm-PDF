import uuid

import pytest
from fastapi import HTTPException

from backend.main import generated_pdf_storage_path

COMPANY, USER, HISTORY = (str(uuid.uuid4()) for _ in range(3))


def test_path_uses_keys_returned_by_get_current_user():
    # get_current_user exposes company_id / auth_user_id / id, never `sub` or `app_metadata`
    user = {"id": USER, "auth_user_id": USER, "company_id": COMPANY}
    assert generated_pdf_storage_path(user, HISTORY) == f"{COMPANY}/{USER}/{HISTORY}.pdf"


def test_path_never_contains_none_segments():
    for user in ({}, {"id": USER}, {"id": USER, "company_id": "local_company"}):
        with pytest.raises(HTTPException) as exc:
            generated_pdf_storage_path(user, HISTORY)
        assert exc.value.status_code == 400


def test_supabase_company_id_reads_get_current_user_keys():
    from backend.main import supabase_company_id
    assert supabase_company_id({"company_id": COMPANY}) == COMPANY
    assert supabase_company_id({"company_id": "local_company", "jwt_company_id": COMPANY}) == COMPANY
    assert supabase_company_id({"app_metadata": {"company_id": COMPANY}}) == COMPANY
    assert supabase_company_id({"company_id": "local_company"}) is None
    assert supabase_company_id(None) is None


def test_company_data_queries_supabase_when_session_has_company(monkeypatch):
    import backend.main as m
    monkeypatch.setattr(m, "APP_ENVIRONMENT", "local")
    seen = {}

    class Q:
        def __init__(self, table): self.table_name = table
        def select(self, *_): return self
        def eq(self, col, val): seen.setdefault(self.table_name, {})[col] = val; return self
        def single(self): return self
        def limit(self, *_): return self
        def execute(self):
            row = {"razon_social": "ACME SAS", "nit": "900123", "dv": "4"} if self.table_name == "companies" else None
            return type("R", (), {"data": row if self.table_name == "companies" else []})()

    client = type("C", (), {"table": lambda self, t: Q(t)})()
    data = m.load_company_data_for_generation({"company_id": COMPANY}, client)
    assert data["razon_social"] == "ACME SAS" and data["nit"] == "900123-4"
    assert seen["companies"]["id"] == COMPANY


def test_company_data_falls_back_to_local_json_without_supabase_company(monkeypatch):
    import backend.main as m
    monkeypatch.setattr(m, "APP_ENVIRONMENT", "local")
    data = m.load_company_data_for_generation({"company_id": "local_company"}, object())
    assert "razon_social" in data


def test_company_data_production_requires_company(monkeypatch):
    import backend.main as m
    monkeypatch.setattr(m, "APP_ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as exc:
        m.load_company_data_for_generation({"company_id": "local_company"}, object())
    assert exc.value.status_code == 403
