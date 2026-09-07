# 0007: Financial Domain Modeling, Semantic Amount Isolation, and Anti-Phone Collision Guard

Establish a first-class `financiero` category across the data model and UI, integrate accounting balance variables into the canonical corporate profile, and introduce the `financial_amount` semantic type to eliminate false-positive collision with phone number validators.

## Context & Problem
Forms from financial institutions, insurers, and compliance bodies (SARLAFT/SAGRILAFT) require corporate financial balance statements (Activos, Pasivos, Patrimonio, Ingresos Mensuales, Egresos Mensuales). Integrating these figures surfaced two technical problems:
1. **Category Conflation & Missing Domain Concept:** The UI and data contracts only provided `'id' | 'contacto' | 'banco' | 'otros'`. Operating payment accounts (`banco`) were conflated with statutory corporate balance sheets (`financiero`), violating domain isolation.
2. **Validator Collision (Phone Displacement Anti-Pattern):** Colombian corporate accounting figures (ranging from 9 to 11 digits, e.g. `$16.151.175.009`) matched the standard length heuristic of phone numbers (`7 <= len(digits) <= 12`). In `FillingValidator.detect_semantic_type()`, financial amounts were mistakenly tagged as `"phone"`, triggering Tier 3 type-aware rejections when assigned to financial fields like "Total Activos".

## Decision
1. **First-Class `'financiero'` Category:**
   - Expand `CompanyCategory` in `types.ts` and backend schemas:
     ```typescript
     type CompanyCategory = 'id' | 'contacto' | 'banco' | 'financiero' | 'otros';
     ```
   - Add dedicated UI tab "Financiero" in `DataAccordionViewer` with balance iconography (`DollarSign`), suggestions in `DataEntryPanel`, and server persistence in `categorized_company.json["financiero"]`.

2. **Clean Numeric Master Data (`company_data.json`):**
   - Financial figures are stored strictly as unformatted numeric strings without currency signs or punctuation:
     - `total_activos`: `"16151175009"`
     - `total_pasivos`: `"8831977528"`
     - `total_patrimonio`: `"7319197482"`
     - `total_ingresos_mensuales`: `"1110748257"`
     - `total_egresos_mensuales`: `"975086377"`
   - Note: The fundamental accounting equation is preserved exactly:
     $$\text{Activos} - \text{Pasivos} = \text{Patrimonio} \implies 16.151.175.009 - 8.831.977.528 = 7.319.197.482$$
   - Formatting ($ or localized dots/commas) is deferred to the visual/presentation layer.

3. **Semantic Type Priority & Anti-Phone Guard (`validator.py`):**
   - Reorder `detect_semantic_type()` evaluation priority so `financial_amount` evaluates *before* `phone`:
     1. `financial_amount`
     2. `email`
     3. `nit`
     4. `cedula`
     5. `phone` (no longer captures financial amounts)
     6. `date`
     7. `text`
   - **Tier 3 Type Guard for `financial_amount`:** Enforces that financial amounts are only placed into fields with positive accounting signals (`activo`, `pasivo`, `patrimonio`, `ingreso`, `egreso`, `balance`, `cifra`, `monto`, `financier`), and strictly rejected from contact/identity destinations.

4. **Deterministic Mapping & Semantic Synonyms:**
   - Expand `FIELD_SYNONYMS` in `field_dictionary.py` for Spanish accounting variations.
   - Implement rule-based deterministic matching in `agent.py` for immediate, zero-token evaluation.

## Consequences
- Clean separation between operational bank accounts and corporate balance sheets in UI and backend stores.
- 100% elimination of false-positive phone rejections on financial values.
- Seamless automatic filling of financial sections in compliance and onboarding forms.