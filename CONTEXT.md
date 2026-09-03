# CONTEXT.md — Ubiquitous Language & Domain Glossary

This document defines the core concepts and vocabulary used across the **AutoForm PDF (SmartFormAI)** project.

---

## 1. Core Domain Concepts

### Form Types
- **AcroForm (Interactive PDF)**: A PDF containing native fillable form widgets (Text, CheckBox, RadioButton, ComboBox).
- **Flat PDF (Visual Form)**: A standard, non-interactive PDF without form fields, requiring coordinate-based visual placement overlay.
- **Scanned / Image PDF**: A PDF without an extractable text layer, requiring OCR or Multimodal Vision processing.

### Responsive UI & Workspace Layout (ADR-0004)
- **Collapsible Rail Sidebar**: Two-state lateral panel: Expanded (340px full view) and Rail Mode (48px icon tab view) ensuring maximum PDF canvas real-estate on compact displays.
- **Elastic Ribbon Toolbar**: Formatting bar with an auto-constrained text input (`min-width: 140px; max-width: 320px`) and non-destructive horizontal smooth scrolling, guaranteeing permanent access to media tools ("Agregar Imagen", "Añadir Texto").
- **Smart Action Collapse**: Priority navbar breakpoint behavior (`<= 1280px`) collapsing secondary actions ("Datos Empresa", "Guardar Mapeo", "Limpiar") to compact icon buttons, guaranteeing that the primary conversion action ("Generar PDF") remains fully expanded and visible.

### Validation, Protection & Audit Reporting (ADR-0001, ADR-0002, ADR-0005)
- **`FillingValidator`**: The centralized three-tier verification engine that inspects every proposed field value before writing to any document format.
- **Negative Zones (Lista Negra Canónica)**: Mandatory non-fillable regions (PEP, Bank/Entity internal use, Customer-only, Spouses/secondary beneficiaries, International ops/debt, Fund origin declaration, Nacionalidad 2 / doble nacionalidad).
- **Green Zones Whitelist**: Canonical priority sections (`INFORMACIÓN GENERAL`, `DATOS BÁSICOS`, `REPRESENTANTE LEGAL`, `CONTACTO SÓLO PARA PROVEEDORES`, `SOCIOS/ACCIONISTAS` [fila 0], `Firma`) where field coverage is strictly enforced with zero omitted values.
- **Single-Row Enforcement**: Structural constraint restricting multi-row grid forms to index 0 (Row 1 only) to eliminate duplication.
- **Type-Aware Guard**: Post-match semantic verification barrier that maps values to strict data types (`phone`, `email`, `nit`, `cedula`, `country`, `nationality`, `person_name`, `date`, `text`) and rejects assignments to conflicting destination labels.
- **Value Displacement**: Anti-pattern where values leak into adjacent or wrongly mapped fields (e.g., placing Nationality into Phone). Eradicated by the Type-Aware Guard.
- **Local-First Label Hierarchy**: Evaluation order prioritizing native widget labels and inline `left_text` over `above_text`, eliminating cross-row header contamination.
- **Per-Section Multi-Occurrence `(category, section)`**: Granular category uniqueness allowing required identifiers (e.g., NIT, email) to populate both Company Info and Contact sections without mutual blocking.
- **`UNFILLED_FIELDS_AUDIT`**: Structured audit report generated per filling run, detailing count of filled fields, policy-blocked fields (Negative Zones), and unfilled candidates needing `company_data.json` enrichment.
- **Declarative In-line Sequence**: Pattern for inline authorization paragraphs (`"Yo, [Nombre]... identificado con [Tipo] No. [Cédula] de [Expedición]"`), mapped sequentially without skipping fields.
- **Compound Label Priority**: Resolution strategy for merged labels: if containing `"Nombres y Apellidos"`, prioritize the Legal Representative; if strictly `"Razón Social"`, prioritize the Company Name.

### Confidence Scoring & Collision Resolution (ADR-0003)
- **Three-Band Hybrid Confidence Scoring**: Matcher grading mechanism:
  - **Banda 1 (Score $\ge 0.85$ - Green)**: Immediate deterministic assignment. Bypasses LLM.
  - **Banda 2 ($0.60 \le \text{Score} < 0.85$ - Yellow)**: Grey-zone candidate forwarded to LLM with Top 3 candidate categories and section context for arbitration.
  - **Banda 3 (Score $< 0.60$ - Red)**: Noise rejection floor. Discarded immediately without LLM consultation.
- **Max-Score Collision Arbitration**: Principle resolving multi-field contention for a single profile category: the highest-scoring field wins the primary value; evicted fields receive available secondary data or remain empty.
- **`COLLISION_NO_SECONDARY`**: Actionable telemetry log generated when an evicted field has no remaining secondary profile data, flagging candidates for `company_data.json` enrichment.

### Filling Modes & Processing
- **Deterministic Matcher (`_deterministic_acroform_match`)**: High-priority rule-based mapper that pairs form labels with company profile fields directly via regex and fuzzy keyword matching (+22 canonical rules), bypassing the LLM when certainty is high.
- **LLM Mapper (`_fill_acroform`)**: Progressive chunk-by-chunk Azure OpenAI mapping pass (using `gpt-4.1-mini`) for ambiguous or unmapped fields, strictly filtered through `FillingValidator`.
- **Visual Placement (`VisualPlacement`)**: Text or image overlay coordinates `(x, y, w, h, page)` applied to render atop a flat PDF.
- **Draw-to-Map**: Interactive frontend canvas mode where users draw bounding boxes directly over PDF cells to bind variables.
- **Progressive Disclosure**: UI pattern in the Data Manager separating entry categorization (`ID`, `Contacto`, `Banco`, `Otros`) from preview accordions.

---

## 2. Shared Data Entities
- **`company_profile` (`company_data.json`)**: Single source of truth containing official corporate data (NIT, Razón Social, Representante Legal, Cédula, Bancos). Grounding rule: if not present in this file, it must never be written. Nationality is strictly standardized to `"Colombia"`.
- **`field_dictionary.py`**: Semantic synonyms mapping real corporate profile keys to common Colombian form variations, alongside exclusion rules.
- **`KnowledgeBase` (`knowledge_base.py`)**: CEO persona prompt builder embodying Guillermo Cañón Sarria (CEO of IAC) with Red/Green zone compliance boundaries.
