import re
import unicodedata
from dataclasses import dataclass
from typing import Optional, List, Tuple

@dataclass
class ValidationResult:
    is_valid: bool
    reason: str = ""

class FillingValidator:
    """
    Centralized Three-Tier Validation Engine for form filling (AcroForms & Visual Overlays).
    ADR-0001 implementation:
    - Tier 1: Negative Zones / Blacklist
    - Tier 2: Single-Row Enforcement
    - Tier 3: Type-Aware Guard (Anti-Displacement)
    """

    NEGATIVE_ZONE_PHRASES = [
        # PEP
        "pep", "politicamente expuesta", "expuesta politicamente", "persona expuesta",
        # Bank / Entity internal use
        "uso exclusivo", "espacio reservado", "aprobacion interna", "para uso de la entidad",
        "para uso del banco", "uso del banco", "para uso de la oficina", "firma y sello del funcionario",
        # Counterparty / Customer-only
        "solo para clientes", "sólo para clientes", "para clientes", "datos de contacto solo para",
        "solo para vendedores", "solo para proveedor", "solo clientes",
        # Spouses / secondary family
        "conyuge", "compañero permanente", "datos familiares",
        # International operations / foreign debt
        "operaciones internacionales", "endeudamiento externo", "cuentas en el exterior",
        "moneda extranjera", "transacciones en moneda extranjera", "extranjero", "foreign",
        # Fund origin declarations
        "origen de fondos", "origen de recursos", "declaracion de origen",
        "declaración de origen", "actividad economica secundaria", "actividades secundarias"
    ]

    NEGATIVE_FIELD_KEYWORDS = [
        r'\b(otra|otro|otras|otros)\b'
    ]

    def _normalize(self, text: Optional[str]) -> str:
        if not text:
            return ""
        norm = unicodedata.normalize('NFKD', str(text)).encode('ASCII', 'ignore').decode('utf-8')
        return re.sub(r'[^a-zA-Z0-9\s]', ' ', norm).lower().strip()

    def detect_semantic_type(self, value: str) -> str:
        """
        Infers semantic type of a proposed string value:
        phone, email, nit, cedula, country, date, person_name, text
        """
        val_str = str(value).strip()
        val_norm = self._normalize(val_str)
        digits_only = re.sub(r'\D', '', val_str)

        # Date: YYYY-MM-DD or DD/MM/YYYY
        if re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}$', val_str) or re.match(r'^\d{2}[-/]\d{2}[-/]\d{4}$', val_str):
            return "date"

        # Email
        if "@" in val_str and "." in val_str:
            return "email"

        # Country
        if val_norm in ["colombia", "republica de colombia"]:
            return "country"

        # Nationality
        if val_norm in ["colombiana", "colombiano"]:
            return "nationality"

        # Phone: 7-12 digits without letters
        if len(digits_only) >= 7 and len(digits_only) <= 12 and not re.search(r'[a-zA-Z]', val_str):
            return "phone"

        # Person Name
        if any(name_part in val_norm for name_part in ["guillermo humberto", "canon sarria", "kelly yohana", "delgado macea"]):
            return "person_name"

        # Company Name
        if "ingenieria asistida por computador" in val_norm:
            return "company_name"

        return "text"

    def validate(
        self,
        label: str,
        section: str,
        field_name: str,
        proposed_value: str
    ) -> ValidationResult:
        """
        Runs the 3-tier validation sequence on a proposed field-value pair.
        """
        val_str = str(proposed_value).strip()
        if not val_str:
            return ValidationResult(is_valid=False, reason="Empty value")

        context_text = f"{label} {section} {field_name}".strip()
        norm_context = self._normalize(context_text)
        norm_label = self._normalize(label)
        norm_section = self._normalize(section)

        # --- TIER 1: Negative Zones / Blacklist ---
        for phrase in self.NEGATIVE_ZONE_PHRASES:
            phrase_norm = self._normalize(phrase)
            if phrase_norm in norm_section or phrase_norm in norm_context:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 1 Negative Zone: Matched forbidden section/phrase '{phrase}'"
                )

        for pat in self.NEGATIVE_FIELD_KEYWORDS:
            if re.search(pat, norm_label) and not any(k in norm_context for k in ["razon social", "representante legal"]):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 1 Negative Field Keyword: '{pat}'"
                )

        # --- TIER 2: Single-Row Enforcement ---
        # Find all occurrences of row indices across segments: e.g. Fila1[1], Row[2], Item[3], .Row2, .Fila2
        for match in re.finditer(r'(?:fila|row|item)\w*\[(\d+)\]', field_name, re.IGNORECASE):
            if int(match.group(1)) > 0:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 2 Single-Row Enforcement: Row index {match.group(1)} > 0 is blocked"
                )

        # Secondary check for 1-based named rows: .Row2, .Fila2, Fila2[0]
        for match in re.finditer(r'(?:fila|row|item)(\d+)', field_name, re.IGNORECASE):
            if int(match.group(1)) > 1:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 2 Single-Row Enforcement: Row index {match.group(1)} > 1 is blocked"
                )

        # --- TIER 3: Type-Aware Guard (Anti-Displacement) ---
        sem_type = self.detect_semantic_type(val_str)

        # 3.1 Phone values must not go into non-phone fields
        if sem_type == "phone":
            # Target must have phone signals, and NOT non-phone keywords
            forbidden_phone_targets = ["pais", "ciudad", "email", "correo", "nit", "nombre", "apellido", "razon social"]
            if any(k in norm_label for k in forbidden_phone_targets):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 3 Type-Aware Guard: Phone value cannot be assigned to '{norm_label}'"
                )

        # 3.2 Country values (e.g., 'Colombia') must NEVER go to phone, email, nit, person_name, dir
        if sem_type == "country":
            forbidden_country_targets = ["cel", "tel", "movil", "telefono", "email", "correo", "nit", "direccion", "nombre", "apellido"]
            if any(k in norm_label for k in forbidden_country_targets):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 3 Type-Aware Guard: Country value '{val_str}' cannot be assigned to phone/contact field '{norm_label}'"
                )
            if not any(k in norm_label for k in ["pais", "nacion", "republica", "origen", "domicilio"]):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 3 Type-Aware Guard: Country value '{val_str}' requires country label, found '{norm_label}'"
                )

        # 3.3 Nationality values (e.g., 'Colombiana') strictly to nationality fields
        if sem_type == "nationality":
            if "nacionalidad" not in norm_label and "nacionalidad" not in norm_context:
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 3 Type-Aware Guard: Nationality value cannot be assigned to non-nationality field '{norm_label}'"
                )

        # 3.4 Person names must not go into nationality, country, nit, phone
        if sem_type == "person_name":
            forbidden_name_targets = ["nacionalidad", "pais", "nit", "tel", "cel", "telefono", "correo", "email"]
            if any(k in norm_label for k in forbidden_name_targets):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 3 Type-Aware Guard: Person name '{val_str}' cannot be assigned to '{norm_label}'"
                )

        # 3.5 Email values must go to email fields
        if sem_type == "email":
            if not any(k in norm_label for k in ["email", "correo", "e mail"]):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 3 Type-Aware Guard: Email '{val_str}' cannot be assigned to non-email field '{norm_label}'"
                )

        # 3.6 Date values must go to date fields
        if sem_type == "date":
            if not any(k in norm_label for k in ["fecha", "date", "nacimiento", "constitucion", "expedicion"]):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 3 Type-Aware Guard: Date '{val_str}' cannot be assigned to non-date field '{norm_label}'"
                )

        return ValidationResult(is_valid=True, reason="Passed all 3 tiers")
