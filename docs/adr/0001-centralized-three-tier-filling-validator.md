# 0001: Centralized Three-Tier Form Filling Validation (FillingValidator)

To eradicate value displacement (e.g., placing country names into phone fields), repetitive multi-row population, and unintended compliance entries, form filling across both AcroForms and Visual Overlays is governed by a unified three-tier validation engine (`FillingValidator`).

## Context & Problem
In automated document filling with multimodal LLMs and fuzzy string heuristics, two primary failure modes repeatedly occurred:
1. **Value Displacement:** Semantically mismatched values were assigned to adjacent fields when context was ambiguous (e.g., `celular: "Colombia"` or `nacionalidad: "Guillermo Humberto"`).
2. **Table Overflow & Repetition:** Repetitive subforms (rows 1..n for shareholders, references, accounts) were filled redundantly with single-instance company data.
3. **Negative Zone Breaches:** Sections reserved for counterparties, compliance declarations (PEP, Origen de Fondos), or internal bank approval were inadvertently filled.

## Decision
1. **Three-Tier Architecture:**
   - **Tier 1 (Negative Zones Filter):** Pure structural and text blacklist. Completely rejects fields belonging to PEP, bank/entity internal use, customer-only sections, spouse/secondary beneficiaries, international ops, or fund origin declarations.
   - **Tier 2 (Single-Row Enforcement):** Hard constraint blocking table row indices `> 0` (Row 1 only) across all tabular widgets by default.
   - **Tier 3 (Type-Aware Guard):** Strict semantic type barrier evaluating both value format and destination label compatibility matrix (`phone`, `email`, `nit`, `cedula`, `country`, `person_name`, `date`, `text`). Rejects assignments that violate negative keyword constraints (e.g., country string mapped to phone/nit label, or date mapped to non-date label).
2. **Unified Core Module:** Both the AcroForm engine (`_fill_acroform`) and the flat PDF engine (`_fill_visual`) must route all proposed field assignments through the same `FillingValidator` before mutating the document.
3. **Strict Company Data Grounding:** Only fields explicitly defined in `company_data.json` may be written. The system never infers or invents external compliance statements (e.g., fund origins are left blank for human declaration).

## Consequences
- Impossible for values like "Colombia" or names to leak into phone or numeric slots.
- LLM acts solely as a proposal engine; it possesses zero authority to bypass semantic type guards or negative zone blacklists.
- Single source of truth for filling constraints, eliminating code divergence between interactive and visual overlay modes.
