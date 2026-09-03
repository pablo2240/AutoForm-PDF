# 0003: Hybrid Confidence Scoring & Collision Resolution

Introduce a three-band hybrid confidence scoring engine with collision arbitration and eviction telemetry (`COLLISION_NO_SECONDARY`).

## Context & Problem
While rule-based deterministic matching and negative zone guards eliminated illegal assignments, form fields exhibited two subtle vulnerabilities:
1. **Unranked Field Matching:** Matching was binary (all-or-nothing regex). Minor spelling variations or multi-word labels were either matched indiscriminately or missed completely, forcing reliance on the LLM for simple label variations.
2. **Duplicate Target Contention (Collisions):** When multiple fields on a page contended for the same logical category (e.g., two contact numbers competing for `celular`), the first one encountered greedily consumed the primary value without regard to match quality.

## Decision
1. **Three-Band Hybrid Confidence Scoring:**
   - **Banda 1 (Score >= 0.85 - Green):** Immediate deterministic assignment. The field label matches a known canonical synonym with high token/sequence similarity. Bypasses the LLM entirely.
   - **Banda 2 (0.60 <= Score < 0.85 - Yellow):** Grey-zone candidate. Filtered and forwarded to Azure OpenAI LLM accompanied by the **Top 3** highest-scoring candidate categories and section context for contextual arbitration.
   - **Banda 3 (Score < 0.60 - Red):** Noise rejection floor. Any field scoring below 0.60 is rejected immediately to avoid polluting the LLM context with weak candidates.
2. **Max-Score Collision Arbitration & Eviction:**
   - When two or more fields on a form compete for the same profile category, the field with the **highest confidence score** wins the primary value.
   - The evicted field is evaluated for an available, semantically valid secondary value (e.g. assigning secondary phone `2656868` if primary cellular `3104120217` was won by a higher-scoring field).
3. **Structured Telemetry (`COLLISION_NO_SECONDARY`):**
   - If an evicted field has no valid secondary value in `company_data.json`, it is left empty and explicitly logged:
     `[WARN] COLLISION_NO_SECONDARY: Field '{field_name}' (score={score}) evicted from category '{category}'. No secondary value available.`
   - This provides actionable insight for expanding `company_data.json` over time.
4. **Post-Match Type Guard Barrier:**
   - Even high-confidence matches (>= 0.85) must still pass the centralized `FillingValidator` (Tier 1 Negative Zones, Tier 2 Single-Row Enforcement, Tier 3 Type-Aware Guard) before mutation.

## Consequences
- Deterministic match rate increases without risking hallucinations or value displacement.
- Eliminates non-deterministic collisions when multiple candidate fields exist.
- Creates an audit trail of unfulfilled fields for future data enrichment.
