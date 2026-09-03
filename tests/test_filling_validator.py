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
        proposed_value="Colombiana"
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
