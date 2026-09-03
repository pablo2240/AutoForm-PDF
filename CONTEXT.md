# CONTEXT.md — Ubiquitous Language & Domain Glossary

This document defines the core concepts and vocabulary used across the **AutoForm PDF (SmartFormAI)** project.

---

## 1. Core Domain Concepts

### Form Types
- **AcroForm (Interactive PDF)**: A PDF containing native fillable form widgets (Text, CheckBox, RadioButton, ComboBox).
- **Flat PDF (Visual Form)**: A standard, non-interactive PDF without form fields, requiring coordinate-based visual placement overlay.
- **Scanned / Image PDF**: A PDF without an extractable text layer, requiring OCR or Multimodal Vision processing.

### Filling Modes & Processing
- **Deterministic Matcher (`_deterministic_acroform_match`)**: High-priority rule-based mapper that pairs form labels with company profile fields directly via regex and fuzzy keyword matching (+22 canonical rules), bypassing the LLM when certainty is high.
- **LLM Mapper (`_fill_acroform`)**: Progressive chunk-by-chunk Azure OpenAI mapping pass (using `gpt-4.1-mini`) for ambiguous or unmapped fields.
- **Visual Placement (`VisualPlacement`)**: Text or image overlay coordinates `(x, y, w, h, page)` applied to render atop a flat PDF.
- **Draw-to-Map**: Interactive frontend canvas mode where users draw bounding boxes directly over PDF cells to bind variables.
- **Progressive Disclosure**: UI pattern in the Data Manager separating entry categorization (`ID`, `Contacto`, `Banco`, `Otros`) from preview accordions.

### Exclusion Rules & Compliance
- **PEP (Persona Expuesta Políticamente)**: Compliance section in Colombian corporate forms that must remain strictly unfilled.
- **Solo para Clientes / Proveedores**: Form sections intended only for counterparties or customers that must be ignored when filling as a vendor/supplier.
- **Value Displacement**: An anti-pattern where values leak into adjacent or wrongly mapped fields (e.g., placing Nationality into Phone). Prevented via strict label matching and isolated category assignment.

---

## 2. Shared Data Entities
- **`company_profile` (`company_data.json`)**: Single source of truth containing official corporate data (NIT, Razón Social, Representante Legal, Cédula, Bancos).
- **`field_dictionary.py`**: Semantic synonyms mapping real corporate profile keys to common Colombian form variations, alongside exclusion rules.
- **`KnowledgeBase` (`knowledge_base.py`)**: CEO persona prompt builder embodying Guillermo Cañón Sarria (CEO of IAC) with Red/Green zone compliance boundaries.
