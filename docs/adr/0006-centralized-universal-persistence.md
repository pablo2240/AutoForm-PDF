# 0006: Centralized Universal Persistence, Backend Asset Management, and Strict Authoritative State

Establish dedicated backend persistence for company data, employer profiles, categorized metadata, and physical signature assets, enforcing a strict Backend-Authoritative state model across all client browsers and sessions.

## Context & Problem
Previously, corporate data persistence and digital signatures suffered from fragmented client-side isolation:
1. **Isolated Signature State (`localStorage`):** The global digital signature (`GlobalSignature`) was stored solely in the client browser's `localStorage` as a base64 string. Opening the application in a different browser, incognito session, or secondary device resulted in missing signatures. Furthermore, large image payloads caused silent failures or `QuotaExceededError` (5MB quota).
2. **PyMuPDF Inefficiency:** The backend PDF generation engine had no predictable physical asset on disk for the signature. It depended on receiving ad-hoc base64 strings decoded per visual placement request.
3. **Disjointed Employer Profiles & Categories:** Structured categories (`id`, `contacto`, `banco`, `otros`) and additional employer profiles (`EmployerProfile[]`) were kept in `localStorage`, while `company_data.json` on disk only stored an un-categorized flat dictionary.
4. **Client Initialization Race & Inconsistencies:** On app boot, `App.tsx` attempted a bidirectional merge between local browser cache and `GET /api/company-data`. If one browser had outdated or stale entries in `localStorage`, it contaminated or diverged from the server state.

## Decision
1. **Physical Signature Asset Storage & Dedicated REST Endpoints:**
   - Signatures are physically stored on the server under `backend/data/signatures/global_signature.png`.
   - Dedicated REST routes:
     - `GET /api/signature`: Returns `{ "filename": "global_signature.png", "url": "/api/signature/image", "position": {...}, "size": {...}, "exists": true }`.
     - `GET /api/signature/image`: Serves the binary PNG directly (`FileResponse`) with cache-busting headers.
     - `POST /api/signature`: Receives signature payload (`image_base64`, `filename`, `position`, `size`), writes the binary image directly to disk, and saves metadata in `backend/data/signature_metadata.json`.
     - `DELETE /api/signature`: Deletes the physical file and metadata when cleared.
   - **PyMuPDF Direct Disk Loading:** The visual stamping engine (`VisualPDFProcessor` / `VisualPlacement`) can load the signature directly from `backend/data/signatures/global_signature.png` without per-request base64 decoding overhead.

2. **Dedicated Backend Collections for Profiles and Categories:**
   - To preserve single responsibility, `company_data.json` remains the clean, flat contract consumed by `FillingValidator`, AcroForms, and the LLM agent.
   - Dedicated endpoints and storage files:
     - `backend/data/categorized_company.json` (`GET /api/categorized-company`, `POST /api/categorized-company`).
     - `backend/data/employer_profiles.json` (`GET /api/employer-profiles`, `POST /api/employer-profiles`).
   - Saving in the Data Manager modal synchronizes categories and profiles to their respective files, and regenerates the canonical flat `company_data.json`.

3. **Strict Backend-Authoritative State (No Business `localStorage`):**
   - `localStorage` is completely eradicated from company data, employer profiles, and signature storage.
   - **App Load (`init`):** Fetches authoritative state directly from backend endpoints via `Promise.all([fetchTemplates(), fetchCompanyData(), fetchCategorizedCompany(), fetchEmployerProfiles(), fetchSignature()])`.
   - **Editing:** In-memory React state modification only (non-persistent draft).
   - **Save:** Explicit user action triggers `POST /api/*` to write to disk and commit to React state.
   - **Discard:** Reloading or closing without saving discards in-memory modifications cleanly.

## Consequences
- **True Multi-Browser Parity:** Any browser (Chrome, Edge, Firefox, Safari, Mobile, Incognito) displays identical corporate variables, profiles, and signatures.
- **Zero Local Quota Failures:** Large high-resolution signatures do not fail due to browser storage limits.
- **Clean Architecture:** `company_data.json` remains lightweight and single-purpose; rich UI categories and multi-person profiles live in dedicated server collections.
- **Faster PDF Processing:** PyMuPDF accesses physical image assets directly from the filesystem.