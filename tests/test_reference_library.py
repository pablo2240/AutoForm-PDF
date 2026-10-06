import json
import os

import fitz
import numpy as np
import pytest

from backend.pdf_filling_agent.reference_library import (
    ReferenceLibrary, build_fewshot, format_fewshot_block,
)
from backend.pdf_filling_agent.reference_library.embeddings import HashingEmbedder

PROVEEDOR = ["Razón social", "NIT", "Representante legal", "Correo electrónico", "Dirección", "Teléfono"]
BANCARIO = ["Banco", "Número de cuenta", "Tipo de cuenta", "Sucursal", "Titular de la cuenta", "Moneda"]
RECETA = ["Nombre del plato", "Tiempo de cocción", "Número de porciones", "Nivel de dificultad", "Calorías por porción"]


def make_form(path, labels, section="1. INFORMACIÓN GENERAL"):
    """Synthetic AcroForm: a section title and `label: [widget]` rows."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 40), section, fontsize=12)
    y = 70
    for i, label in enumerate(labels):
        text = label + ":"
        page.insert_text((195 - fitz.get_text_length(text, fontsize=10), y + 12), text, fontsize=10)
        w = fitz.Widget()
        w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        w.field_name = f"Text{i}"
        w.rect = fitz.Rect(220, y, 500, y + 16)
        page.add_widget(w)
        y += 34
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def refs(tmp_path):
    root = tmp_path / "referencias"
    for family, labels, name in (("proveedor", PROVEEDOR, "a.pdf"), ("bancario", BANCARIO, "b.pdf")):
        (root / family).mkdir(parents=True)
        make_form(root / family / name, labels)
    return root


@pytest.fixture
def lib(tmp_path, refs):
    return ReferenceLibrary(db_path=str(tmp_path / "lib.db"), references_dir=str(refs),
                            manifest_path=str(tmp_path / "manifest.json"))


def test_sync_is_incremental_and_tracks_provenance(lib, refs):
    first = lib.sync()
    assert sorted(first["added"]) == ["bancario/b.pdf", "proveedor/a.pdf"] and not first["errors"]
    assert lib.sync()["unchanged"] and not lib.sync()["added"]

    make_form(refs / "proveedor" / "a.pdf", PROVEEDOR + ["Página web"])  # file changed on disk
    assert lib.sync()["updated"] == ["proveedor/a.pdf"]

    (refs / "otros").mkdir()
    make_form(refs / "otros" / "c.pdf", RECETA)
    assert lib.sync()["added"] == ["otros/c.pdf"]
    os.remove(refs / "otros" / "c.pdf")
    assert lib.sync()["removed"] == ["otros/c.pdf"]
    assert {d["family"] for d in lib.store.list_documents()} == {"proveedor", "bancario"}


def test_manifest_overrides_folder_family(lib, tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"families": {"a.pdf": "cliente"}}), encoding="utf-8")
    lib.sync()
    assert lib.store.get_document("proveedor/a.pdf")["family"] == "cliente"


def test_add_and_remove_document(lib, tmp_path):
    src = make_form(tmp_path / "nuevo.pdf", RECETA)
    with open(src, "rb") as f:
        out = lib.add_document("nuevo.pdf", f.read(), family="Receta Cocina")
    assert out["doc_id"] == "receta_cocina/nuevo.pdf"
    assert lib.store.get_document(out["doc_id"])["n_widgets"] == len(RECETA)
    assert lib.remove_document(out["doc_id"]) and lib.store.get_document(out["doc_id"]) is None
    with pytest.raises(ValueError):
        lib.remove_document("../../etc/passwd")
    with pytest.raises(ValueError):
        lib.add_document("x.txt", b"hi")


def test_search_returns_provenance_and_semantic_matches(lib):
    lib.sync()
    hits = lib.search("Identificación fiscal", top_k=8)
    assert hits[0]["concept"] == "nit" and hits[0]["similarity"] > 0.8
    ref = [o for h in hits for o in h["occurrences"] if o["document"] == "a.pdf"]
    assert ref and ref[0]["family"] == "proveedor" and len(ref[0]["rect"]) == 4 and ref[0]["section"].startswith("1.")
    assert lib.search("Código interno", top_k=3, min_similarity=0.6) == []
    assert all(o["family"] == "bancario" for h in lib.search("Banco", family="bancario") for o in h["occurrences"])


def test_classification_known_vs_unknown(lib, tmp_path):
    lib.sync()
    nuevo = make_form(tmp_path / "n1.pdf", ["Nombre o razón social", "NIT", "Correo", "Dirección", "Teléfono", "Representante legal"])
    cls = lib.classify_pdf(nuevo)
    assert cls.is_known and cls.family == "proveedor" and cls.strategy == "family"
    assert cls.shares[0]["share"] > 0.6 and cls.nearest_documents[0]["doc_id"] == "proveedor/a.pdf"

    desconocido = make_form(tmp_path / "n2.pdf", RECETA + ["Talla de camiseta", "Fecha del evento"])
    cls = lib.classify_pdf(desconocido)
    assert not cls.is_known and cls.family is None and cls.strategy == "unknown"


def test_classification_ignores_file_name(lib, tmp_path):
    lib.sync()
    misleading = make_form(tmp_path / "formulario_bancario_cuenta.pdf", PROVEEDOR)
    assert lib.classify_pdf(misleading).family == "proveedor"


def test_fewshot_respects_top_k_skips_master_model_and_formats(lib):
    lib.sync()
    widgets = [{"field_name": "Text0", "label": "Nombre legal de la compañía"},
               {"field_name": "Text1", "label": "Identificación fiscal"},
               {"field_name": "Text2", "label": "Numero de la cuenta bancaria"}]
    ex = build_fewshot(lib, widgets, top_k=1, min_similarity=0.5)
    assert ex and all(e["document"] in ("a.pdf", "b.pdf") for e in ex)  # reference forms, never the dictionary
    for fn in {e["field_name"] for e in ex}:
        assert sum(1 for e in ex if e["field_name"] == fn) <= 1
    assert len(build_fewshot(lib, widgets, top_k=5, max_examples=2, min_similarity=0.5)) <= 2
    block = format_fewshot_block(ex, family="proveedor", confidence=0.8)
    assert "REFERENCE KNOWLEDGE" in block and "profile key" in block and "proveedor" in block
    assert format_fewshot_block([]) == ""


def test_changing_embedder_reembeds_without_reparsing(lib):
    lib.sync()
    before = len(lib.store.label_matrix(lib.embedder.name)[0])

    class Tiny(HashingEmbedder):
        name = "tiny-test"

        def __init__(self):
            super().__init__(dim=64)

    lib.embedder = Tiny()
    report = lib.sync()
    assert report["unchanged"] and not report["added"]  # PDFs untouched
    ids, matrix = lib.store.label_matrix("tiny-test")
    assert len(ids) == before and matrix.shape[1] == 64
    assert lib.search("NIT")[0]["concept"] == "nit"


def test_propagation_never_overwrites_trusted_concepts(lib):
    lib.sync()
    rows = lib.store.document_occurrences(include_builtin=True)
    assert any(r["concept"] == "nit" for r in rows)
    lib.sync(force=True)  # re-propagating must be idempotent
    assert {r["concept"] for r in lib.store.document_occurrences(include_builtin=True)} >= {"nit", "razon_social"}


# ---- agent integration (no network: the LLM is stubbed) -------------------------------------
@pytest.fixture
def agent_env(monkeypatch, tmp_path, refs):
    import backend.pdf_filling_agent.reference_library.library as libmod
    monkeypatch.setattr(libmod, "_default", None)
    monkeypatch.setattr(libmod, "_default_failed", False)
    monkeypatch.setenv("REFERENCE_LIBRARY_DIR", str(refs))
    monkeypatch.setenv("REFERENCE_LIBRARY_DB", str(tmp_path / "agent.db"))
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")


def _run_agent(tmp_path, labels):
    from backend.pdf_filling_agent.agent import PDFAgent
    prompts = []
    agent = PDFAgent(company_profile={"razon_social": "ACME SAS", "nit": "9001234567"})
    agent._call_llm = lambda messages, token_limit=2000: prompts.append(messages[-1]["content"]) or "{}"
    pdf = make_form(tmp_path / "entrada.pdf", labels)
    (tmp_path / "out").mkdir(exist_ok=True)
    agent.fill_pdf(pdf, "llena", output_dir=str(tmp_path / "out"))
    return agent, prompts


def test_agent_injects_dynamic_fewshot_and_reports_family(agent_env, tmp_path):
    agent, prompts = _run_agent(tmp_path, ["Denominación de la compañía", "Identificación fiscal del contribuyente", "Domicilio"])
    assert prompts and "REFERENCE KNOWLEDGE" in prompts[0]
    assert "reference documents" not in prompts[0] and "%PDF" not in prompts[0]
    ref = agent.last_audit_report["reference_library"]
    assert ref["fewshot_examples"] >= 1 and ref["strategy"] in ("family", "unknown")


def test_agent_unchanged_when_library_disabled(agent_env, monkeypatch, tmp_path):
    monkeypatch.setenv("REFERENCE_LIBRARY_ENABLED", "0")
    agent, prompts = _run_agent(tmp_path, ["Denominación de la compañía", "Identificación fiscal del contribuyente"])
    assert prompts and all("REFERENCE KNOWLEDGE" not in p for p in prompts)
    assert "reference_library" not in agent.last_audit_report


def test_agent_survives_library_failure(agent_env, monkeypatch, tmp_path):
    import backend.pdf_filling_agent.reference_library.library as libmod
    monkeypatch.setattr(libmod.ReferenceLibrary, "sync", lambda self, force=False: (_ for _ in ()).throw(RuntimeError("boom")))
    agent, prompts = _run_agent(tmp_path, ["Denominación de la compañía"])
    assert prompts and "reference_library" not in agent.last_audit_report


def test_admin_api(agent_env, monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.auth_supabase import require_admin
    from backend.reference_api import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/api/reference-library").status_code in (401, 403)  # admin only

    app.dependency_overrides[require_admin] = lambda: {"id": "admin"}
    assert client.get("/api/reference-library").json()["documents"] == 2
    pdf = make_form(tmp_path / "up.pdf", RECETA)
    with open(pdf, "rb") as f:
        r = client.post("/api/reference-library/documents", files={"file": ("up.pdf", f.read(), "application/pdf")}, data={"family": "recetas"})
    assert r.status_code == 200 and r.json()["doc_id"] == "recetas/up.pdf"
    assert client.post("/api/reference-library/documents", files={"file": ("x.pdf", b"nope", "application/pdf")}).status_code == 400
    assert client.get("/api/reference-library/search", params={"q": "NIT"}).json()["results"][0]["concept"] == "nit"
    with open(pdf, "rb") as f:
        assert client.post("/api/reference-library/classify", files={"file": ("up.pdf", f.read(), "application/pdf")}).json()["family"] == "recetas"
    assert client.delete("/api/reference-library/documents/recetas/up.pdf").status_code == 200
    assert client.delete("/api/reference-library/documents/recetas/up.pdf").status_code == 404
