import pytest
from backend.pdf_filling_agent.validator import FillingValidator, ValidationResult

@pytest.fixture
def validator():
    return FillingValidator()

# --- TIER 1: Negative Zones / Blacklist ---
def test_negative_zone_pep(validator):
    res = validator.validate(
        label="¿Es usted una Persona Expuesta Políticamente?",
        section="6. PERSONA EXPUESTA POLÍTICAMENTE (PEP)",
        field_name="pep_radio_1",
        proposed_value="NO"
    )
    assert not res.is_valid
    assert "Negative Zone" in res.reason

def test_negative_zone_bank_use(validator):
    res = validator.validate(
        label="Firma funcionario",
        section="ESPACIO PARA USO EXCLUSIVO DEL BANCO",
        field_name="txt_funcionario",
        proposed_value="Aprobado"
    )
    assert not res.is_valid
    assert "Negative Zone" in res.reason

def test_negative_zone_client_only(validator):
    res = validator.validate(
        label="Recibo de mercancía",
        section="2. DATOS DE CONTACTO SÓLO PARA CLIENTES",
        field_name="contacto_cliente",
        proposed_value="Guillermo Humberto Cañón Sarria"
    )
    assert not res.is_valid
    assert "Negative Zone" in res.reason

def test_negative_zone_fund_origin(validator):
    res = validator.validate(
        label="Detalle el origen de los recursos",
        section="DECLARACIÓN DE ORIGEN DE FONDOS Y RECURSOS",
        field_name="origen_fondos",
        proposed_value="Giro ordinario"
    )
    assert not res.is_valid
    assert "Negative Zone" in res.reason

def test_negative_zone_spouse(validator):
    res = validator.validate(
        label="Nombres y Apellidos del Cónyuge o Compañero Permanente",
        section="DATOS FAMILIARES Y CÓNYUGE",
        field_name="conyuge_nombre",
        proposed_value="Kelly Delgado"
    )
    assert not res.is_valid
    assert "Negative Zone" in res.reason

# --- TIER 2: Single-Row Enforcement ---
def test_single_row_allowed_row_0(validator):
    res = validator.validate(
        label="Nombre del Socio",
        section="COMPOSICIÓN ACCIONARIA",
        field_name="TablaAccionistas[0].Fila1[0].Nombre[0]",
        proposed_value="Guillermo Humberto Cañón Sarria"
    )
    assert res.is_valid

def test_single_row_blocked_row_1(validator):
    res = validator.validate(
        label="Nombre del Socio",
        section="COMPOSICIÓN ACCIONARIA",
        field_name="TablaAccionistas[0].Fila1[1].Nombre[0]",
        proposed_value="Guillermo Humberto Cañón Sarria"
    )
    assert not res.is_valid
    assert "Single-Row Enforcement" in res.reason

def test_single_row_blocked_row_2(validator):
    res = validator.validate(
        label="Referencia Comercial",
        section="REFERENCIAS",
        field_name="Subform[5].Row2.Nombre",
        proposed_value="Empresa XYZ"
    )
    assert not res.is_valid
    assert "Single-Row Enforcement" in res.reason

# --- TIER 3: Type-Aware Guard (Displacement Prevention) ---
def test_type_guard_rejects_country_in_phone(validator):
    # The exact bug reported by user: celular: Colombia
    res = validator.validate(
        label="Teléfono Celular",
        section="1. DATOS GENERALES",
        field_name="txt_celular",
        proposed_value="Colombia"
    )
    assert not res.is_valid
    assert "Type-Aware Guard" in res.reason

def test_type_guard_accepts_valid_phone(validator):
    res = validator.validate(
        label="Celular:",
        section="1. DATOS GENERALES",
        field_name="txt_celular",
        proposed_value="3104120217"
    )
    assert res.is_valid

def test_type_guard_rejects_phone_in_country(validator):
    res = validator.validate(
        label="País de Domicilio",
        section="1. DATOS GENERALES",
        field_name="txt_pais",
        proposed_value="3104120217"
    )
    assert not res.is_valid

def test_type_guard_rejects_name_in_nationality(validator):
    res = validator.validate(
        label="Nacionalidad",
        section="1.2 DATOS REPRESENTANTE LEGAL",
        field_name="txt_nacionalidad",
        proposed_value="Guillermo Humberto"
    )
    assert not res.is_valid

def test_type_guard_accepts_valid_nationality(validator):
    res = validator.validate(
        label="Nacionalidad",
        section="1.2 DATOS REPRESENTANTE LEGAL",
        field_name="txt_nacionalidad",
        proposed_value="Colombia"
    )
    assert res.is_valid

def test_type_guard_rejects_email_in_phone(validator):
    res = validator.validate(
        label="Teléfono fijo",
        section="1. DATOS GENERALES",
        field_name="txt_tel",
        proposed_value="guillermo.canon@iaclatam.com"
    )
    assert not res.is_valid

def test_type_guard_rejects_date_in_non_date_field(validator):
    res = validator.validate(
        label="Número de identificación",
        section="1. DATOS GENERALES",
        field_name="txt_id",
        proposed_value="1985-03-21"
    )
    assert not res.is_valid

def test_negative_zone_rejects_nacionalidad_2(validator):
    res = validator.validate(
        label="Nacionalidad 2",
        section="1.2 DATOS REPRESENTANTE LEGAL",
        field_name="txt_nacionalidad_2",
        proposed_value="Colombia"
    )
    assert not res.is_valid
    assert "Negative Zone" in res.reason

def test_negative_zone_rejects_doble_nacionalidad(validator):
    res = validator.validate(
        label="Segunda Nacionalidad",
        section="1.2 DATOS REPRESENTANTE LEGAL",
        field_name="txt_otra_nacionalidad",
        proposed_value="Colombia"
    )
    assert not res.is_valid
    assert "Negative Zone" in res.reason

def test_green_zone_allows_proveedores_contact(validator):
    res = validator.validate(
        label="Nombre del contacto comercial",
        section="3. DATOS DE CONTACTO SÓLO PARA PROVEEDORES",
        field_name="contacto_proveedor",
        proposed_value="Guillermo Humberto Cañón Sarria"
    )
    assert res.is_valid

def test_type_guard_accepts_colombia_as_nationality_value(validator):
    res = validator.validate(
        label="Nacionalidad 1",
        section="1.2 DATOS REPRESENTANTE LEGAL",
        field_name="txt_nacionalidad_1",
        proposed_value="Colombia"
    )
    assert res.is_valid

# --- ADR-0003: Confidence Scoring & Collision Arbitration Tests ---
def test_confidence_score_exact_match(validator):
    from backend.pdf_filling_agent.field_dictionary import FIELD_SYNONYMS
    # 'Número de Identificación Tributaria' matches synonym in FIELD_SYNONYMS['nit']
    best_cat, score, top3 = validator.score_field(
        label="Número de Identificación Tributaria",
        field_name="txt_nit",
        synonyms_dict=FIELD_SYNONYMS
    )
    assert best_cat == "nit"
    assert score >= 0.85  # Banda 1: Green

def test_confidence_score_grey_zone(validator):
    from backend.pdf_filling_agent.field_dictionary import FIELD_SYNONYMS
    # A label that is partially similar (e.g. 'Denominación Social Empresa')
    best_cat, score, top3 = validator.score_field(
        label="Denominación Social de la Entidad",
        field_name="txt_denominacion",
        synonyms_dict=FIELD_SYNONYMS
    )
    assert best_cat == "razon_social"
    assert 0.60 <= score < 0.85  # Banda 2: Yellow (forwarded with top 3)
    assert len(top3) <= 3

def test_confidence_score_rejection_floor(validator):
    from backend.pdf_filling_agent.field_dictionary import FIELD_SYNONYMS
    # Random non-matching text
    best_cat, score, top3 = validator.score_field(
        label="Volumen de ventas en miles de unidades trimestrales",
        field_name="txt_volumen",
        synonyms_dict=FIELD_SYNONYMS
    )
    assert score < 0.60  # Banda 3: Red (Noise rejection)

def test_collision_arbitration_highest_score_wins(validator):
    # Two fields contend for 'celular_rep'
    field_a = {"name": "txt_celular_directo", "label": "Teléfono Celular", "score": 0.95}
    field_b = {"name": "txt_telefono_movil", "label": "Móvil", "score": 0.72}

    profile = {
        "celular_rep": "3104120217",
        "telefono": "2656868"
    }

    resolved = validator.resolve_collisions(
        proposals=[
            (field_a["name"], field_a["label"], "celular_rep", profile["celular_rep"], field_a["score"]),
            (field_b["name"], field_b["label"], "celular_rep", profile["celular_rep"], field_b["score"])
        ],
        profile=profile
    )

    # Winner gets primary
    assert resolved[field_a["name"]] == "3104120217"
    # Evicted gets secondary phone
    assert resolved.get(field_b["name"]) == "2656868"

def test_collision_no_secondary_leaves_empty_and_logs(validator, capsys):
    # Two fields contend for 'nit', which has no secondary value
    field_a = {"name": "txt_nit_1", "label": "NIT", "score": 0.98}
    field_b = {"name": "txt_nit_2", "label": "Identificación Tributaria", "score": 0.86}

    profile = {
        "nit": "8110047212"
    }

    resolved = validator.resolve_collisions(
        proposals=[
            (field_a["name"], field_a["label"], "nit", profile["nit"], field_a["score"]),
            (field_b["name"], field_b["label"], "nit", profile["nit"], field_b["score"])
        ],
        profile=profile
    )

    assert resolved[field_a["name"]] == "8110047212"
    assert field_b["name"] not in resolved  # Evicted and left empty
    captured = capsys.readouterr().out
    assert "COLLISION_NO_SECONDARY" in captured

# --- ADR-0005: Audit Reporting & Recall Tests ---
def test_audit_reporting_categorizes_filled_unfilled_and_blocked(validator):
    widgets = [
        {"field_name": "txt_razon", "label": "Razón Social", "section": "1. INFORMACIÓN GENERAL"},
        {"field_name": "txt_fax_sec", "label": "Número de Fax", "section": "1. INFORMACIÓN GENERAL"},
        {"field_name": "pep_radio_1", "label": "¿Es usted PEP?", "section": "6. PERSONA EXPUESTA POLÍTICAMENTE (PEP)"}
    ]

    filled_map = {
        "txt_razon": "Ingeniería Asistida Por Computador S.A.S"
    }

    audit = validator.generate_audit_report(widgets, filled_map)

    assert audit["filled"] == 1
    # Check blocked by negative zone
    blocked_names = [b["field"] for b in audit["blocked"]]
    assert "pep_radio_1" in blocked_names
    assert audit["blocked"][0]["reason"] == "NEGATIVE_ZONE"

    # Check unfilled due to missing data in profile
    unfilled_names = [u["field"] for u in audit["unfilled"]]
    assert "txt_fax_sec" in unfilled_names
    assert audit["unfilled"][0]["reason"] == "NO_DATA_IN_JSON"
    assert "suggestion" in audit["unfilled"][0]


def test_pn_field_force_blanked_in_accionaria(validator):
    """Field 01 'Nombres y apellidos PN' is left empty — the name goes into field 02 (PJ).
    The validator accepts person names in PJ fields; the force-blank is enforced at agent level."""
    # The validator itself does not block this — the agent's force_blank_fields handles it.
    # We just confirm the PJ field correctly accepts the name.
    res_pj = validator.validate(
        label="Nombre Persona Jurídica",
        section="ANEXO DE COMPOSICIÓN ACCIONARIA",
        field_name="02",
        proposed_value="Guillermo Humberto Cañón Sarria"
    )
    assert res_pj.is_valid, f"Expected valid but got: {res_pj.reason}"


def test_single_row_rejects_is_secondary_row(validator):
    res = validator.validate(
        label="Nombre Persona Jurídica",
        section="ANEXO DE COMPOSICIÓN ACCIONARIA",
        field_name="03",
        proposed_value="Ingeniería Asistida Por Computador S.A.S",
        is_secondary_row=True
    )
    assert not res.is_valid
    assert "Single-Row" in res.reason


def test_type_aware_rejects_percentage_in_identificacion(validator):
    res = validator.validate(
        label="Identificación (NIT/CC)",
        section="ANEXO DE COMPOSICIÓN ACCIONARIA",
        field_name="39",
        proposed_value="100%"
    )
    assert not res.is_valid
    assert "Percentage" in res.reason


def test_row_1_shareholder_mappings_valid(validator):
    """Row 1: name in PJ field (02) and cédula in identification field (38) must both be valid."""
    res_pj = validator.validate(
        label="Nombre Persona Jurídica",
        section="ANEXO DE COMPOSICIÓN ACCIONARIA",
        field_name="02",
        proposed_value="Guillermo Humberto Cañón Sarria"
    )
    assert res_pj.is_valid, f"Expected valid but got: {res_pj.reason}"

    res_cedula = validator.validate(
        label="Identificación (NIT/CC)",
        section="ANEXO DE COMPOSICIÓN ACCIONARIA",
        field_name="38",
        proposed_value="98555384"
    )
    assert res_cedula.is_valid, f"Expected valid but got: {res_cedula.reason}"


def test_beneficiarios_finales_row_1_valid(validator):
    """Row 1 of Beneficiarios Finales: person name and cédula must both be valid."""
    res_name = validator.validate(
        label="Clic para escribir el nombre del beneficiario final",
        section="ANEXO – Información de Beneficiarios Finales",
        field_name="Indique el nombre del beneficiario final 1",
        proposed_value="Guillermo Humberto Cañón Sarria"
    )
    assert res_name.is_valid, f"Expected valid but got: {res_name.reason}"

    res_cedula = validator.validate(
        label="Clic para escribir el No. De Identificación",
        section="ANEXO – Información de Beneficiarios Finales",
        field_name="Indique el número de identificación 1",
        proposed_value="98555384"
    )
    assert res_cedula.is_valid, f"Expected valid but got: {res_cedula.reason}"


def test_beneficiarios_finales_secondary_rows_blocked(validator):
    """Rows 2+ of Beneficiarios Finales must be blocked under single-row table policy."""
    res_sec_name = validator.validate(
        label="Clic para escribir el nombre del beneficiario final",
        section="ANEXO – Información de Beneficiarios Finales",
        field_name="Indique el nombre del beneficiario final 2",
        proposed_value="Guillermo Humberto Cañón Sarria",
        is_secondary_row=True
    )
    assert not res_sec_name.is_valid
    assert "Single-Row" in res_sec_name.reason


def test_isagen_ariba_persona_autorizada_person_name_allowed(validator):
    """Person name must be allowed in ARIBA Text1 even if incidental text mentions 'correo'."""
    label = (
        "constituyen manifestacion valida de su voluntad tenga en cuenta que el los correo s "
        "reportado s seran los unicos a traves de los cuales nombres y apellidos persona autorizada"
    )
    res = validator.validate(
        label=label,
        section="DATOS CONTACTO PARA ARIBA *",
        field_name="Text1",
        proposed_value="Guillermo Humberto Cañón Sarria"
    )
    assert res.is_valid, f"Expected valid but got: {res.reason}"


def test_ariba_persona_autorizada_email_blocks_person_name(validator):
    """Person name must be rejected for actual email fields (Text5 / correo electronico)."""
    label_email = "voluntad * los cuales podra recibir invitaciones o presentar ofertas. Correo electronico"
    res = validator.validate(
        label=label_email,
        section="DATOS CONTACTO PARA ARIBA *",
        field_name="Text5",
        proposed_value="Guillermo Humberto Cañón Sarria"
    )
    assert not res.is_valid
    assert "Person name" in res.reason and "cannot be assigned" in res.reason


