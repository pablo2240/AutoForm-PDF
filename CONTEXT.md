# CONTEXT.md — Ubiquitous Language & Domain Glossary

This document defines the core concepts and vocabulary used across the **AutoForm PDF (SmartFormAI)** project.

---

## 1. Core Domain Concepts

### Form Types
- **AcroForm (Interactive PDF)**: A PDF containing native fillable form widgets (Text, CheckBox, RadioButton, ComboBox).
- **Flat PDF (Visual Form)**: A standard, non-interactive PDF without form fields, requiring coordinate-based visual placement overlay.
- **Scanned / Image PDF**: A PDF without an extractable text layer, requiring OCR or Multimodal Vision processing.

### Validation & Protective Barriers
- **`FillingValidator`**: The centralized three-tier verification engine that inspects every proposed field value before writing to any document format.
- **Negative Zones (Lista Negra Canónica)**: Mandatory non-fillable regions (PEP, Bank/Entity internal use, Customer-only, Spouses/secondary beneficiaries, International ops/debt, Fund origin declaration).
- **Single-Row Enforcement**: Structural constraint restricting multi-row grid forms to index 0 (Row 1 only) to eliminate duplication.
- **Type-Aware Guard**: Post-match semantic verification barrier that maps values to strict data types (`phone`, `email`, `nit`, `cedula`, `country`, `person_name`, `date`, `text`) and rejects assignments to conflicting destination labels.
- **Value Displacement**: Anti-pattern where values leak into adjacent or wrongly mapped fields (e.g., placing Nationality into Phone). Eradicated by the Type-Aware Guard.

### Filling Modes & Processing
- **Deterministic Matcher (`_deterministic_acroform_match`)**: High-priority rule-based mapper that pairs form labels with company profile fields directly via regex and fuzzy keyword matching (+22 canonical rules), bypassing the LLM when certainty is high.
- **LLM Mapper (`_fill_acroform`)**: Progressive chunk-by-chunk Azure OpenAI mapping pass (using `gpt-4.1-mini`) for ambiguous or unmapped fields, strictly filtered through `FillingValidator`.
- **Visual Placement (`VisualPlacement`)**: Text or image overlay coordinates `(x, y, w, h, page)` applied to render atop a flat PDF.
- **Draw-to-Map**: Interactive frontend canvas mode where users draw bounding boxes directly over PDF cells to bind variables.
- **Progressive Disclosure**: UI pattern in the Data Manager separating entry categorization (`ID`, `Contacto`, `Banco`, `Otros`) from preview accordions.

---

## 2. Shared Data Entities
- **`company_profile` (`company_data.json`)**: Single source of truth containing official corporate data (NIT, Razón Social, Representante Legal, Cédula, Bancos). Grounding rule: if not present in this file, it must never be written.
- **`field_dictionary.py`**: Semantic synonyms mapping real corporate profile keys to common Colombian form variations, alongside exclusion rules.
- **`KnowledgeBase` (`knowledge_base.py`)**: CEO persona prompt builder embodying Guillermo Cañón Sarria (CEO of IAC) with Red/Green zone compliance boundaries.
