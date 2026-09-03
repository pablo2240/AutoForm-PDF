# 0002: Green Zones Whitelist, Declarative Sequences, and Exact Field Value Policies

Establish explicit Green Zones for high-recall form filling, deterministic declarative paragraph handling ("Yo, ..."), compound name resolution, and standardized country/nationality strings.

## Context & Problem
While ADR-0001 solved negative zones and type displacement, practical usage highlighted four specific areas requiring precise alignment:
1. **Nationality Standardization:** The country value was occasionally formatted as "Colombiana", whereas enterprise business requirements mandate the exact country string "Colombia". Additionally, multi-nationality fields ("Nacionalidad 2") must remain unfilled.
2. **Declarative In-line Sequences:** Authorization/declaration paragraphs beginning with phrases like "Yo, [name], identificado con [doc_type] No. [id] de [expedition]..." had skipped fields due to lack of explicit label associations on in-line underline widgets.
3. **Compound Label Ambiguity:** Compound labels containing both person and company hints (`Nombres y Apellidos / Razón Social`) created confusion between legal representative and company name.
4. **Omission in Core Sections (Recall Gaps):** Core sections were occasionally under-filled when the agent was overly conservative.

## Decision
1. **Nationality Standardization:**
   - Single source of truth for nationality is `"Colombia"` (matching country).
   - "Nacionalidad 2" and any secondary nationality slots are explicitly classified as Negative Zones and kept 100% empty.
2. **Declarative In-line Sequence Engine:**
   - In-line statement widgets following anchors (`"Yo,"`, `"El suscrito"`, `"identificado con"`, `"No."`, `"de"`) must be mapped sequentially:
     - Person Name: `"Guillermo Humberto Cañón Sarria"`
     - Document Type: `"C.C."`
     - ID Number: `"98555384"`
     - Expedition Place: `"Envigado"`
3. **Compound Label Priority Rules:**
   - If the label contains `"Nombres y Apellidos"` (e.g. `"Nombres y Apellidos / Razón Social"`), prioritize the Legal Representative: `"Guillermo Humberto Cañón Sarria"`.
   - If the label is strictly `"Razón Social"` or `"Nombre o Razón Social"`, prioritize the Company: `"Ingeniería Asistida Por Computador S.A.S"`.
4. **Green Zones Whitelist (High Recall):**
   - The following canonical sections are whitelisted for exhaustive filling (zero skipped fields for available company data):
     - `INFORMACIÓN GENERAL` / `DATOS BÁSICOS` / `DATOS BÁSICOS DEL SOLICITANTE`
     - `DATOS REPRESENTANTE LEGAL` / `Representante Legal`
     - `INFORMACIÓN BÁSICA DE LA PERSONA JURÍDICA`
     - `DATOS DE CONTACTO SÓLO PARA PROVEEDORES`
     - `SOCIOS Y/O ACCIONISTAS` / `ACCIONISTAS CON PARTICIPACIÓN` / `Beneficiarios Finales` (Row 0 only)
     - `Firma del Representante Legal`

## Consequences
- Guarantees 100% fill coverage in critical corporate sections without skipping fields like email, NIT, or IDs.
- Eliminates "Colombiana" vs "Colombia" discrepancies.
- Fully automates legal declaration headers ("Yo, Guillermo Humberto Cañón Sarria...").
