# 0008: Commercial Profiles Domain, Neon PostgreSQL Persistence, and Habeas Data Protection

Establish the `CommercialProfile` (Responsable Comercial) domain model backed by managed PostgreSQL on Neon, replace ephemeral JSON file stores with Alembic migrations, enforce conscious selection of commercial liaisons across UI and API, and protect personal identity numbers (`documento_identidad`) under Colombian Habeas Data (Ley 1581 de 2012).

## Context & Problem
Client and vendor registration forms commonly mandate a "Persona de Contacto / Asesor Comercial / Tramitador" with distinct contact attributes (full name, position, direct corporate email, cellular phone, and occasionally identity document) alongside the statutory Legal Representative (`Guillermo Cañón Sarria`).

Supporting multi-operator commercial personas exposed four architectural and regulatory challenges:
1. **Render Ephemeral Filesystem & Race Conditions:** Storing and mutating files (`employer_profiles.json`) directly on Render results in silent data loss during sleep cycles, dyno restarts, or new deployments unless a persistent paid disk is attached. Furthermore, concurrent updates by multiple operators overwrite entire JSON collections.
2. **Access Friction vs. Operational Realities:** Enforcing user accounts (Login / Register) creates operational friction: administrative assistants or executive officers frequently diligence forms on behalf of different commercial reps (e.g. Kelly Delgado).
3. **Habeas Data & Personal Data Exposure (Ley 1581 de 2012):** Adding personal identification numbers (`documento_identidad`) to unauthenticated public endpoints creates immediate regulatory compliance violations. Identification numbers must not be exposed over public selector APIs or cached in client-side storage (`sessionStorage`).
4. **Displacement Hazard & Unintentional Filling:** Generating a form without an explicit choice between a commercial liaison and the statutory legal representative risks stamping incorrect contact personas onto compliance documents.

## Decision

### 1. Relational Persistence via Managed PostgreSQL (Neon) & Alembic
- Adopt serverless PostgreSQL on **Neon** as the authoritative relational store for commercial contact personas.
- Manage schema migrations through **Alembic**, executed strictly as a `preDeployCommand` in Render before application container boot:
  ```bash
  alembic upgrade head
  ```
- **Fail-Fast Environment Policy:** `DATABASE_URL` is mandatory in production. The backend fails fast on startup if `DATABASE_URL` is absent. Local SQLite fallback is permitted strictly when `ENVIRONMENT=development`.
- Seed Kelly Delgado idempotently via migration to preserve existing corporate baseline data.

### 2. Domain Model (`CommercialProfile`)
```python
class CommercialProfile(Base):
    __tablename__ = "commercial_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_name = Column(String(100), nullable=False)   # e.g. "Kelly Delgado"
    nombre = Column(String(100), nullable=False)         # "Kelly Yohana"
    apellido = Column(String(100), nullable=False)       # "Delgado Macea"
    cargo = Column(String(100), nullable=False)          # "Asesor Comercial"
    email = Column(String(150), nullable=False)          # "Kelly.Delgado@iaclatam.com"
    celular = Column(String(50), nullable=False)         # "301 4750760"
    tipo_documento = Column(String(20), default="C.C")
    documento_identidad = Column(String(50), nullable=True)  # Sensitive - strictly guarded
    is_active = Column(Boolean, default=True, nullable=False) # Soft-delete
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_modified_by_ip = Column(String(45), nullable=True)
```

### 3. Habeas Data Privacy & DTO Separation
- **Public Selector Endpoint (`GET /api/commercial-profiles`):**
  - Read-only, unauthenticated endpoint utilized by the React header selector.
  - **Public DTO:** Exposes strictly `id`, `profile_name`, `cargo`, `email`, `celular`, and `is_active`.
  - `documento_identidad` is completely excluded from the Pydantic serialization schema.
- **Server-Side Identity Resolution for PDF Generation:**
  - The client transmits solely `{ "commercial_profile_id": "<uuid>" }` in the `/api/generate` payload.
  - FastAPI resolves the commercial record directly from Neon PostgreSQL and passes values internally to PyMuPDF. Identification numbers never cross the public network to client browsers.
- **Administrative Endpoints (`/api/admin/commercial-profiles/*`):**
  - Mutations (create, edit, soft-delete) and unmasked identity queries require an authenticated administrative session via an `HttpOnly`, `SameSite=Strict`, `Secure` session cookie backed by `ADMIN_PASSWORD`.

### 4. Conscious Selection Workflow & API Defense
- **Header Selector UI:**
  - Prominently positioned in the React application header:
    `👤 Contacto comercial: [ Selecciona un responsable ▼ ] [Gestionar]`
  - Dropdown options display `profile_name` and `cargo` (e.g. *"Kelly Delgado — Asesor Comercial"*), alongside an explicit option: *"Sin contacto comercial (Solo Representante Legal)"*.
  - Initial selection state is empty (`null`).
  - `sessionStorage` caches strictly the `active_commercial_profile_id` string, never personal PII.
- **Two-Sided Enforcement:**
  - **Frontend Guard:** "Generar PDF" is disabled with an explanatory tooltip until the operator actively selects a commercial profile or chooses "Solo Representante Legal".
  - **Backend API Guard:** `/api/generate` validates `commercial_profile_id`. If omitted, null, or invalid, FastAPI aborts immediately with `HTTP 422 Unprocessable Entity`.

### 5. Three-Zone Form Demarcation (`agent.py`)
1. **Zona Legal / Corporativa / Declaraciones:** Always filled with statutory legal representative data (`Guillermo Cañón Sarria`) from `company_data.json`.
2. **Zona Bancaria / Financiera:** Always filled with company bank accounts and balance sheets.
3. **Zona de Contacto / Comercial:** Filled with the resolved active `CommercialProfile` (or fallback to Legal Representative if `"legal_rep_only"`).

## Consequences
- **Zero Data Loss on Render:** Relational data survives redeployments, dyno restarts, and scaling without paid disk attachments.
- **Regulatory Compliance:** Strict compliance with Colombian Habeas Data (Ley 1581 de 2012) through DTO projection and server-side PDF stamping.
- **Zero Operational Collision:** Multi-operator concurrency supported cleanly without file-write race conditions.
- **Form Integrity:** Unintentional displacement or misattribution of commercial contact roles is completely eliminated.
