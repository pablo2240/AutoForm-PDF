import fitz
import pytest

from backend.pdf_filling_agent.agent import PDFAgent
from test_reference_library import make_form

PROFILE = {
    "razon_social": "ACME SAS", "nit": "811004721-2", "representante_legal": "Ana Pérez Ruiz",
    "representante_nombre": "Ana", "representante_apellido": "Pérez Ruiz", "numero_cedula": "12345678",
    "correo_rep": "ana@acme.com", "celular_rep": "3001112233",
}


@pytest.fixture
def make_agent(monkeypatch):
    monkeypatch.setenv("REFERENCE_LIBRARY_ENABLED", "0")
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")

    def build(profile=None, commercial=None):
        agent = PDFAgent(company_profile=dict(profile or PROFILE), commercial_profile=commercial)
        agent._call_llm = lambda messages, token_limit=2000: "{}"
        return agent
    return build


def fill(agent, tmp_path, labels):
    pdf = make_form(tmp_path / "f.pdf", labels)
    (tmp_path / "out").mkdir(exist_ok=True)
    out = agent.fill_pdf(pdf, "x", output_dir=str(tmp_path / "out"))
    return {w.field_name: w.field_value for p in fitz.open(out) for w in p.widgets()}, fitz.open(pdf)


@pytest.mark.parametrize("profile,expected", [
    ({"nit": "8110047212"}, ("811004721", "2")),
    ({"nit": "811004721-2"}, ("811004721", "2")),
    ({"nit": "811.004.721 - 2"}, ("811004721", "2")),
    ({"nit": "811004721-2", "nit_digits": "811004721", "dv": "2"}, ("811004721", "2")),
    ({"nit": "8110047212", "dv": "2"}, ("811004721", "2")),
    ({"nit": "900123"}, ("900123", "")),  # unknown DV is never invented
    ({}, ("", "")),
])
def test_split_nit_handles_every_stored_format(profile, expected):
    assert PDFAgent._split_nit(profile) == expected


def test_nit_and_dv_fields_never_get_dashes_or_duplicates(make_agent, tmp_path):
    values, _ = fill(make_agent(), tmp_path, ["NIT", "DV"])
    assert values == {"Campo0": "811004721", "Campo1": "2"}


def test_dv_is_left_empty_when_unknown(make_agent, tmp_path):
    values, _ = fill(make_agent({**PROFILE, "nit": "900123"}), tmp_path, ["NIT", "DV"])
    assert "2" not in values.values() and "-2" not in values.values()


def test_si_no_option_label_is_not_an_id_number_field(make_agent, tmp_path):
    agent = make_agent()
    rich = agent._extract_rich_acro_widgets(fitz.open(make_form(tmp_path / "f.pdf", ["Tipo de Producto", "Número ID"])))
    rich[0]["left_text"] = "Tipo de Producto: SI NO"  # real label from 0-FR-43-001: the trailing NO is a checkbox option
    rich[0]["label"] = rich[0]["left_text"]
    matches, _ = agent._deterministic_acroform_match(rich)
    assert rich[0]["field_name"] not in matches
    assert matches[rich[1]["field_name"]][0] == "12345678"


def test_legal_rep_only_uses_representative_not_a_hardcoded_person():
    contact = PDFAgent._legal_rep_as_contact(PROFILE)
    assert (contact["profile_name"], contact["email"], contact["celular"], contact["cargo"]) == (
        "Ana Pérez Ruiz", "ana@acme.com", "3001112233", "Representante Legal")


def test_llm_prompt_without_commercial_profile_never_mentions_other_people(make_agent, tmp_path):
    agent = make_agent({**PROFILE, "kelly_delgado_nombre_completo": "Kelly Delgado", "kelly_delgado_email": "kelly@x.com"})
    prompts = []
    agent._call_llm = lambda messages, token_limit=2000: prompts.append(messages[-1]["content"]) or "{}"
    fill(agent, tmp_path, ["Campo sin regla conocida", "Otro dato raro"])
    rule = next(line for p in prompts for line in p.splitlines() if line.startswith("16."))
    assert "Ana" in rule and "ana@acme.com" in rule and "Kelly Yohana" not in rule and "kelly.delgado" not in rule
    assert "NUNCA los del Representante Legal" not in rule


def test_commercial_profile_still_wins_when_selected(make_agent, tmp_path):
    cp = {"nombre": "Luis", "apellido": "Mora", "email": "luis@acme.com", "celular": "3150000000", "cargo": "Asesor"}
    agent = make_agent(commercial=cp)
    prompts = []
    agent._call_llm = lambda messages, token_limit=2000: prompts.append(messages[-1]["content"]) or "{}"
    fill(agent, tmp_path, ["Campo sin regla conocida"])
    rule = next(line for p in prompts for line in p.splitlines() if line.startswith("16."))
    assert "Luis Mora" in rule and "NUNCA los del Representante Legal" in rule
