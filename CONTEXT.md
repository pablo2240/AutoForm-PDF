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

### Universal Persistence & Asset Management (ADR-0006)
- **Centralized Universal Persistence**: Backend-hosted Single Source of Truth for corporate data, categorized metadata, employer profiles, and physical signature assets. Eliminates cross-browser divergence and storage quota limitations.
- **Physical Signature Asset (`/api/signature`)**: Server-persisted image (`backend/data/signatures/global_signature.png`) and companion metadata contract, enabling direct PyMuPDF filesystem loading and multi-client access.
- **Backend-Authoritative State**: Architectural principle where all active entities originate exclusively from the backend REST API on application boot. `localStorage` is completely eliminated from business data and signature persistence.
- **Discrete Collection Endpoints**: Segregated server stores (`/api/company-data`, `/api/categorized-company`, `/api/employer-profiles`, `/api/signature`) preserving single responsibility, keeping `company_data.json` flat and pure for filling pipelines.

### Financial Domain & Amount Isolation (ADR-0007)
- **`financial_amount` Semantic Type**: High-priority type-aware semantic barrier ensuring accounting balances (Activos, Pasivos, Patrimonio, Ingresos, Egresos) evaluate *before* phone length heuristics to eliminate false-positive rejections.
- **`financiero` Category**: Dedicated domain category separating corporate statutory balance sheets from operational payment accounts (`banco`).
- **Accounting Invariant**: Corporate balance sheet rule enforced in canonical data: $\text{Activos} - \text{Pasivos} = \text{Patrimonio}$.

### Commercial Profiles & Secure Relational Persistence (ADR-0008, ADR-0009)
- **`CommercialProfile` (Responsable Comercial)**: Designated corporate sales representative or contact liaison. Contains `profile_name`, `nombre`, `apellido`, `cargo`, `email`, `celular`, `ciudad`, and optional sensitive identity `documento_identidad`.
- **Direct Commercial Self-Registration (Auto-Registro Comercial Inmediato)**: Self-service onboarding mechanism allowing commercial advisors with corporate email (`@iaclatam.com` or `@iac.com.co`) to register with strict validation rules (name/apellido >= 4 chars, cargo >= 5 chars, celular 10 digits, cedula 8-11 digits, ciudad >= 3 chars), receiving immediate active status (`is_active: true`, role: `commercial`) and direct session issuance without pending administrative approval queues.
- **Three-Zone Form Demarcation**: Strict separation of target form domains:
  1. *Zona Legal / Corporativa / Declaraciones*: Strictly Legal Representative (`Guillermo Cañón Sarria`).
  2. *Zona Bancaria / Financiera*: Corporate accounts & balance sheets.
  3. *Zona Comercial / Contacto Proveedor*: Active `CommercialProfile` (or fallback to Legal Representative when explicitly `"legal_rep_only"`).
- **Conscious Selection Context**: Header-level workflow enforcing an active choice (`commercial_profile_id` or `"legal_rep_only"`). Unselected states are blocked in the UI and rejected with HTTP 422 in `/api/generate`.
- **Privacy-Preserving DTO Separation (Ley 1581 / Habeas Data)**: Public selector endpoint `GET /api/commercial-profiles` projects strictly public liaison data, excluding `documento_identidad`. Identification numbers are resolved exclusively server-side during PDF stamping or through HttpOnly administrative sessions.
- **Durable Relational Persistence (Neon PostgreSQL)**: Dedicated PostgreSQL persistence decoupling commercial contact data from Render's ephemeral filesystem, managed via Alembic migrations (`preDeployCommand`).

### Password Recovery & Zero-Cost Notification Delivery (ADR-0010)
- **Backend-Authoritative Password Reset (Restablecimiento Autoritativo)**: Centralized recovery engine hosted on FastAPI (`/api/auth/forgot-password`, `/api/auth/verify-reset-token`, and `/api/auth/reset-password`). Bypasses third-party auth limits and executes consistent dual-auth synchronization with Supabase Auth as the primary authoritative identity provider, accompanied by telemetry error logging and pending retry flags for `CommercialProfile.password_hash`.
- **Gmail Dedicated SMTP Transport (Transporte SMTP Dedicado)**: Zero-cost transactional mail delivery utilizing a dedicated system Google account with 16-character App Password (STARTTLS/SSL), ensuring high inbox deliverability without requiring domain DNS modification or third-party paid tiers. Dispatched synchronously with guaranteed process durability against container recycling.
- **Relational Password Reset Token (`password_reset_tokens`)**: Authoritative PostgreSQL entity tracking one-time recovery tokens via SHA-256 hash (`token_hash`), strictly bounded to a 15-minute expiration window (`expires_at`), with explicit single-use audit invalidation (`used_at`) and origin telemetry (`request_ip`). Plaintext tokens are never stored.
- **Consistent Dual-Auth Synchronization with Error Logging and Retry**: Orchestration pattern where Supabase Auth is updated first as primary source of truth. If updating local `password_hash` in PostgreSQL encounters a transient failure, it is recorded as pending synchronization with high-severity logging, ensuring legacy logins do not accept stale passwords.
- **Blind Anti-Enumeration Response**: API design standard returning identical confirmation messages regardless of whether the requested email address exists in the system, preventing external user enumeration.

### Reference Library, Semantic Search & Dynamic Few-Shot (ADR-0013)
- **Reference Library (`referencias/pdf/<familia>/`)**: Folder of example forms that is the source of truth for reusable knowledge. `sync` mirrors it into a derived SQLite cache (SHA-256 change detection); the sub-folder name is the form family unless `referencias/manifest.json` overrides it.
- **Reference Field**: A label found in a reference form together with its provenance (document, page, rect, section, neighbours, example value) and, when known, its master-model concept.
- **Master-Model Concept**: A key of `FIELD_SYNONYMS` / `company_data.json` (`nit`, `razon_social`, ...). Also indexed as the built-in pseudo-document `__modelo_maestro__`.
- **Embedder**: Replaceable label-to-vector provider. `HashingEmbedder` (local, free) by default; `EMBEDDING_PROVIDER=azure|openai` for real semantic embeddings.
- **Form Classification**: Content-based (never file-name-based) estimate of the family a new form belongs to, with per-family shares. Below the confidence gate the form is *unknown* and uses general analysis plus semantic search.
- **Dynamic Few-Shot**: Per-chunk block of the top-k most similar reference fields for the fields the deterministic matcher left unresolved. Hints for the LLM; `FillingValidator` still has the last word.

### Cross-Account Data Isolation & User Workspace Storage (ADR-0011)
- **User Workspace (Espacio de Trabajo de Usuario)**: The strictly isolated, session-scoped execution environment belonging to a single authenticated operator (`auth.uid()`). Completely eliminates global server filesystem state (`/input`, `active_slot.json`).
  _Avoid_: Global workspace, shared slot, public templates directory.
- **User Document (`public.user_documents`)**: Authoritative relational record tracking a PDF file uploaded by an operator, strictly constrained to `(company_id, user_id)` and backed by Supabase Storage (`templates/{company_id}/{user_id}/{filename}.pdf`).
  _Avoid_: Global input file, local server PDF.
- **Single-File Slot (Ranura Única de Usuario)**: The operational guarantee that each operator possesses at most one active working document at any given time, enforced at the database layer via partial unique index (`UNIQUE (user_id) WHERE is_active = true`).
  _Avoid_: Multi-document accumulator, server-side `active_slot.json`.
- **Institutional Template (Plantilla Institucional)**: Company-wide canonical form definition (`pdf_templates`) containing published visual mapping annotations (`pdf_mappings`), cleanly decoupled from private user document instances.
  _Avoid_: User-uploaded raw template.
- **Conditional Hard-Delete (`can_hard_delete`)**: Referential integrity safeguard that verifies all dependent tables (including `form_fill_history`, mappings, and active jobs) before permanently deleting physical storage objects, deactivating superseded records (`is_active = false`) if referenced.
  _Avoid_: Unconditional physical purge, orphaned file deletion.
- **Cross-Account Isolation Guard**: Security barrier enforcing `auth.uid() = user_id OR es_admin(auth.uid())` across all ingestion, listing, rendering, and download pipelines, guaranteeing zero cross-user data leakage.
- **Stateless In-Memory Rendering**: RAM-only PyMuPDF stream processing (`fitz.open(stream=bytes, filetype="pdf")`) that renders pages on-demand without writing temporary files to server disk, coupled with browser-side `ETag` and private caching.
- **Anti-Enumeration Signed Download**: Protected output retrieval pattern (`GET /api/download/{history_id}`) that verifies execution ownership before emitting time-bounded Supabase Storage signed URLs, rejecting unauthorized requests with uniform blind errors.

---

## 2. Shared Data Entities
- **`user_documents` (Supabase PostgreSQL Table)**: Authoritative relational entity managing private user PDF uploads with single-active-slot enforcement and tenant isolation.
- **`company_profile` (`company_data.json`)**: Single source of truth containing official corporate data (NIT, Razón Social, Representante Legal, Cédula, Bancos, Activos, Pasivos, Patrimonio, Ingresos, Egresos). Grounding rule: if not present in this file, it must never be written. Nationality is strictly standardized to `"Colombia"`.
- **`commercial_profiles` (Neon PostgreSQL Table)**: Authoritative relational entity storing commercial representatives with audit columns (`created_at`, `updated_at`, `last_modified_by_ip`) and soft-delete (`is_active`). Replaces legacy ephemeral `employer_profiles.json`.
- **`password_reset_tokens` (Neon PostgreSQL Table)**: Relational audit entity storing SHA-256 hashed recovery tokens with expiration, single-use timestamp (`used_at`), and request IP telemetry.
- **`categorized_company.json`**: UI accordion categorizations (`id`, `contacto`, `banco`, `financiero`, `otros`) persisted independently in the backend.
- **`field_dictionary.py`**: Semantic synonyms mapping real corporate profile keys to common Colombian form variations, alongside exclusion rules.
- **`KnowledgeBase` (`knowledge_base.py`)**: CEO persona prompt builder embodying Guillermo Cañón Sarria (CEO of IAC) with Red/Green zone compliance boundaries.

