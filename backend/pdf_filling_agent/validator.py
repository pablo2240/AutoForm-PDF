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
        # Counterparty / Customer-only (NOTE: 'SOLO PARA PROVEEDORES' is a GREEN ZONE when filling as a provider)
        "solo para clientes", "sólo para clientes", "para clientes", "datos de contacto solo para clientes",
        "solo para vendedores", "solo clientes",
        # Spouses / secondary family
        "conyuge", "compañero permanente", "datos familiares",
        # International operations / foreign debt
        "operaciones internacionales", "endeudamiento externo", "cuentas en el exterior",
        "moneda extranjera", "transacciones en moneda extranjera", "extranjero", "foreign",
        # Fund origin declarations
        "origen de fondos", "origen de recursos", "declaracion de origen",
        "declaración de origen", "actividad economica secundaria", "actividades secundarias",
        # Secondary nationality
        "nacionalidad 2", "segunda nacionalidad", "doble nacionalidad"
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

        # Corporate NIT (e.g. 8110047212 or 811004721)
        if digits_only in ["8110047212", "811004721"]:
            return "nit"

        # Personal ID / Cédula (e.g. 98555384)
        if digits_only == "98555384":
            return "cedula"

        # Phone: 7-12 digits without letters (excluding exact NIT or Cédula)
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
            if not any(k in norm_label for k in ["pais", "nacion", "republica", "origen", "domicilio", "nacionalidad"]):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 3 Type-Aware Guard: Country value '{val_str}' requires country or nationality label, found '{norm_label}'"
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

        # 3.7 NIT values strictly to NIT / Identificación Tributaria fields
        if sem_type == "nit":
            if not any(k in norm_label or k in norm_context for k in ["nit", "rut", "identificacion tributaria", "tributaria"]):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 3 Type-Aware Guard: NIT '{val_str}' requires NIT/RUT field, found '{norm_label}'"
                )

        # 3.8 Cédula values strictly to Cédula / Documento fields
        if sem_type == "cedula":
            if any(k in norm_label for k in ["nit", "rut", "pais", "telefono", "celular", "email", "correo"]):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Tier 3 Type-Aware Guard: Cédula '{val_str}' cannot be assigned to '{norm_label}'"
                )

        return ValidationResult(is_valid=True, reason="Passed all 3 tiers")

    def _token_set_similarity(self, s1: str, s2: str) -> float:
        """
        Calculates balanced token overlap and sequence similarity between two normalized strings.
        Avoids false positives from single-word overlaps while rewarding phrase alignment.
        """
        import difflib
        n1 = self._normalize(s1)
        n2 = self._normalize(s2)
        if not n1 or not n2:
            return 0.0
        if n1 == n2:
            return 1.0

        t1 = set(n1.split())
        t2 = set(n2.split())
        if not t1 or not t2:
            return 0.0

        intersection = t1.intersection(t2)
        if not intersection:
            return difflib.SequenceMatcher(None, n1, n2).ratio()

        # Token overlap metrics: Jaccard and Coverage of the smaller token set
        jaccard = len(intersection) / len(t1.union(t2))
        smaller_len = min(len(t1), len(t2))
        coverage = len(intersection) / smaller_len if smaller_len > 0 else 0.0
        seq_ratio = difflib.SequenceMatcher(None, n1, n2).ratio()

        # Weighted combination: high coverage with partial sequence similarity
        score = (coverage * 0.5) + (jaccard * 0.3) + (seq_ratio * 0.2)
        return min(1.0, max(0.0, score))

    def score_field(
        self,
        label: str,
        field_name: str,
        synonyms_dict: dict
    ) -> Tuple[str, float, List[Tuple[str, float]]]:
        """
        ADR-0003 Three-Band Confidence Scoring:
        Evaluates label + field_name against FIELD_SYNONYMS.
        Returns: (best_category, max_score, top_3_candidates)
        """
        combined = f"{label} {field_name}".strip()
        category_scores: List[Tuple[str, float]] = []

        for category, syn_list in synonyms_dict.items():
            best_cat_score = 0.0
            for syn in syn_list:
                score_label = self._token_set_similarity(label, syn)
                score_field = self._token_set_similarity(field_name, syn)
                score_combined = self._token_set_similarity(combined, syn)
                best_cat_score = max(best_cat_score, score_label, score_field, score_combined)
            category_scores.append((category, round(best_cat_score, 4)))

        # Sort descending by score
        category_scores.sort(key=lambda x: x[1], reverse=True)
        top3 = category_scores[:3]

        best_category = top3[0][0] if top3 else ""
        best_score = top3[0][1] if top3 else 0.0
        return best_category, best_score, top3

    def resolve_collisions(
        self,
        proposals: List[Tuple[str, str, str, str, float]],
        profile: dict
    ) -> dict:
        """
        ADR-0003 Max-Score Collision Arbitration:
        proposals: List of (field_name, label, category, proposed_value, score)
        Resolves contention where multiple fields compete for the same profile category.
        The highest score wins primary. Evicted fields receive secondary or are left empty.
        Logs COLLISION_NO_SECONDARY when evicted field has no secondary.
        """
        # Secondary value mappings for common Colombian profile categories
        SECONDARY_MAP = {
            "celular_rep": "telefono",
            "telefono": "celular_rep",
            "representante_legal": "representante_nombre",
            "numero_cedula": None,
            "nit": None,
            "razon_social": None,
            "nacionalidad": None,
            "pais": None
        }

        # Group proposals by category
        by_category = {}
        for fn, lbl, cat, val, score in proposals:
            by_category.setdefault(cat, []).append((fn, lbl, val, score))

        resolved = {}

        for cat, items in by_category.items():
            # Sort items by score descending
            items.sort(key=lambda x: x[3], reverse=True)
            winner_fn, winner_lbl, winner_val, winner_score = items[0]
            resolved[winner_fn] = winner_val

            # Process evicted candidates
            for evicted_fn, evicted_lbl, evicted_val, evicted_score in items[1:]:
                sec_key = SECONDARY_MAP.get(cat)
                sec_val = profile.get(sec_key) if sec_key else None

                if sec_val:
                    # Validate secondary value with Type-Aware Guard
                    v_res = self.validate(
                        label=evicted_lbl,
                        section="",
                        field_name=evicted_fn,
                        proposed_value=str(sec_val)
                    )
                    if v_res.is_valid:
                        resolved[evicted_fn] = str(sec_val)
                        print(f"[INFO] COLLISION_RESOLVED_SECONDARY: Field '{evicted_fn}' assigned secondary '{sec_key}' = '{sec_val}'")
                    else:
                        print(f"[WARN] COLLISION_NO_SECONDARY: Field '{evicted_fn}' (score={evicted_score}) evicted from category '{cat}'. Secondary '{sec_key}' failed validation: {v_res.reason}")
                else:
                    print(f"[WARN] COLLISION_NO_SECONDARY: Field '{evicted_fn}' (score={evicted_score}) evicted from category '{cat}'. No secondary value available.")

        return resolved

    def generate_audit_report(self, all_widgets: list, filled_map: dict) -> dict:
        """
        ADR-0005: Compiles a structured UNFILLED_FIELDS_AUDIT report.
        Categorizes fields into:
        - filled: Total count of successfully mapped and validated fields.
        - unfilled: Fields in valid zones omitted due to missing profile data (NO_DATA_IN_JSON).
        - blocked: Fields deliberately not filled per security/compliance rules (NEGATIVE_ZONE).
        """
        blocked_list = []
        unfilled_list = []

        for w in all_widgets:
            fn = w.get("field_name", "")
            lbl = w.get("label", fn)
            sec = w.get("section", "")

            # If already filled, skip
            if fn in filled_map:
                continue

            # Check if blocked by Tier 1 Negative Zone
            v_dummy = self.validate(
                label=lbl,
                section=sec,
                field_name=fn,
                proposed_value="TEST_SAMPLE_VALUE"
            )

            if not v_dummy.is_valid and "Negative Zone" in v_dummy.reason:
                blocked_list.append({
                    "field": fn,
                    "label": lbl,
                    "reason": "NEGATIVE_ZONE",
                    "rule": "ADR-0002 Tier 1"
                })
            else:
                # Suggest snake_case field key for profile
                clean_key = self._normalize(lbl).replace(" ", "_")[:30]
                unfilled_list.append({
                    "field": fn,
                    "label": lbl,
                    "reason": "NO_DATA_IN_JSON",
                    "suggestion": f"Agregar '{clean_key}' a company_data.json"
                })

        return {
            "filled": len(filled_map),
            "unfilled": unfilled_list,
            "blocked": blocked_list
        }
