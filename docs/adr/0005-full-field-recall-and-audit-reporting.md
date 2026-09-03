# 0005: Full Field Recall, Local-First Label Priority, and Missing Data Audit Reporting

Establish a local-first label priority resolution hierarchy, per-section multi-occurrence category uniqueness `(category, section)`, and an actionable structured audit reporting pipeline (`UNFILLED_FIELDS_AUDIT`) returned to the user interface.

## Context & Problem
While ADR-0001 through ADR-0004 secured negative zones, type guards, and collision arbitration, field recall still suffered from two structural impediments:
1. **Vertical Label Pollution (above_text over-riding local label):** Widgets whose above text displayed previous row headers (e.g. `NIT` widget with `NOMBRE O RAZÓN SOCIAL` physically above it) triggered the broad `razon_social` matcher before the local `nit` matcher had a chance to evaluate.
2. **Global Category Over-Suppression:** `assigned_categories.add("p_nit")` permanently blocked subsequent legitimate occurrences across different document sections (e.g. `1. INFORMACIÓN GENERAL` vs `3. DATOS DE CONTACTO SÓLO PARA PROVEEDORES`).
3. **Silent Field Omissions:** If a field was in a Green Zone but the required profile key was absent from `company_data.json`, the agent skipped it silently. The user remained unaware of why fields were empty or which profile keys needed to be enriched.

## Decision
1. **Strict Local-First Label Evaluation Hierarchy:**
   Widget label normalization strictly observes the following priority order:
   1. **Native Widget Label / Attribute:** Form field `name` / `title` defined inside the PDF spec.
   2. **Local In-line Text (`left_text`):** Words on the exact same vertical baseline preceding the widget box.
   3. **Fallback Upper Context (`above_text`):** Section headers or field titles above the widget, consulted *only* when levels 1 and 2 yield no recognizable semantic synonym.
   4. **Spatial Neighbor Context:** Surrounding adjacent tokens.
2. **Per-Section Multi-Occurrence Uniqueness `(category, section)`:**
   The uniqueness lock replaces global singletons with a composite tuple `(category_key, normalized_section)`. Legitimate company identifiers (NIT, Email, Phone, Legal Rep) can be written across distinct form sections while still preventing duplicate pollution within the same sub-table or row.
3. **Structured Audit Pipeline (`UNFILLED_FIELDS_AUDIT`):**
   Every filling run compiles an explicit, transparent audit payload returned directly in the response:
   ```json
   {
     "filled": 24,
     "unfilled": [
       {
         "field": "actividad_secundaria",
         "label": "Actividad Económica Secundaria",
         "reason": "NO_DATA_IN_JSON",
         "suggestion": "Agregar 'actividad_secundaria' a company_data.json"
       }
     ],
     "blocked": [
       {
         "field": "pep_radio_1",
         "label": "¿Es usted PEP?",
         "reason": "NEGATIVE_ZONE",
         "rule": "ADR-0002 Tier 1"
       }
     ]
   }
   ```
4. **User-Facing Presentation:**
   The frontend UI presents this audit report in a dedicated summary accordion within the completion modal (`ResultModal`), clearly delineating successful stamps, intentional policy blocks, and recommended profile data additions.

## Consequences
- 100% field recall in all Green Zones where company profile data is present.
- No accidental cross-contamination from vertically adjacent table headers.
- Total transparency: users see exactly what was written, what was protected by safety rules, and what data needs to be added to `company_data.json`.
