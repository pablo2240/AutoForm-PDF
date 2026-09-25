# 0009: Direct Commercial Self-Registration, Strict Validations, and Non-Disruptive Profile Attributes

Establish direct self-service onboarding for commercial advisors, enforce strict format validations across corporate identity attributes, introduce the `ciudad` profile attribute via non-disruptive database migrations, and eliminate intermediate approval states and visual regulatory disclaimers from the registration interface.

## Context & Problem
Previously, commercial accounts were provisioned exclusively through administrative invitations (`POST /api/admin/invite-user`) or through local administrative setups. As commercial team operations expand across diverse corporate branches, requiring manual admin approval for every advisor slows onboarding.

At the same time, vendor registration forms frequently require the commercial representative's city of operation (`ciudad`), a field missing from both `public.profiles` and `commercial_profiles`.

Introducing self-registration and new mandatory profile attributes presents three architectural requirements:
1. **Zero Intermediate Friction:** New commercial accounts must be immediately active (`is_active: true`, role: `commercial`) with instant session establishment upon valid form submission.
2. **Strict Identity Validation & Anti-Abuse:** To prevent dirty corporate data or spam registrations, fields must be strictly validated at both client and server layers (corporate email domain restriction to `@iaclatam.com` / `@iac.com.co`, case-insensitive uniqueness, minimum length thresholds, numeric-only phone and cédula, and rate limiting).
3. **Non-Disruptive Schema Evolution:** Adding `ciudad` must not break or invalidate historical profiles in production that do not yet have a city populated.

## Decision

### 1. Non-Disruptive Schema Migration
- Add `ciudad VARCHAR(100)` to `public.profiles` (Supabase) and `commercial_profiles` (Alembic/PostgreSQL) as a **nullable** column:
  ```sql
  ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS ciudad VARCHAR(100);
  ```
- Historical rows remain valid without backfilling dummy data.
- **Application-Level Enforcement:** All new commercial registrations strictly require `ciudad` (minimum 3 characters, alphabetic with hyphens and periods permitted).

### 2. Strict Domain Validation Rules
The registration DTO and endpoint enforce the following invariants:
- **Email:** Strictly restricted to `@iaclatam.com` and `@iac.com.co`. Case-insensitive uniqueness check (`LOWER(email)`).
- **Nombre & Apellido:** Letters, accents, and spaces only (`^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]{4,}$`), minimum 4 characters each.
- **Cargo:** Alphanumeric, spaces, hyphens, and periods (`^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s\.\-]{5,}$`), minimum 5 characters.
- **Celular:** Strict numeric format with exactly 10 digits (`^\d{10}$`).
- **Cédula (documento_identidad):** Strict numeric format between 8 and 11 digits (`^\d{8,11}$`).
- **Ciudad:** Letters, accents, spaces, hyphens, and periods (`^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\.\-]{3,}$`), minimum 3 characters.
- **Password:** Minimum 6 characters. Passwords are never logged or exposed.
- **Rate Limiting:** Maximum 5 registration attempts per 15-minute sliding window per client IP (`HTTP 429 Too Many Requests`).

### 3. Direct Session Issuance & UI Simplification
- Upon successful validation, the backend persists the profile with `is_active = true`, assigns role `commercial`, links to corporate `company_id`, generates the session token, sets the HttpOnly cookie, and returns the session payload.
- The user is immediately authenticated into the application workspace.
- The `AuthPortal` UI provides direct tab toggling between `Iniciar Sesión` and `Crear Cuenta`.
- The administrative restriction banner and Habeas Data disclaimers are removed from the registration form view, delivering a clean and efficient commercial onboarding experience.

## Consequences

### Positive
- Commercial advisors can onboard autonomously with instant access to the PDF filling workspace.
- High data quality guaranteed by strict multi-tier regex and length validations.
- Non-disruptive migration ensures zero downtime and backward compatibility with existing profile rows.
- Rate limiting protects the registration endpoint from automated enumeration or credential stuffing.

### Negative / Trade-offs
- Historical profile records will have `ciudad` as `NULL` until explicitly updated via profile administration or form fills.
