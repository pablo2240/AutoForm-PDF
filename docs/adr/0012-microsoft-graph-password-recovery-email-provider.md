# 0012: Microsoft Graph Email Provider for Backend-Authoritative Password Recovery

Adopt Microsoft Graph API (`/v1.0/users/{MAIL_SENDER}/sendMail`) with Microsoft Entra ID OAuth2 Client Credentials Grant as the authoritative corporate email transport for AutoForm PDF password recovery in production, replacing Gmail SMTP while preserving single-use cryptographic tokens, blind anti-enumeration responses, and Supabase dual-auth synchronization.

## Context & Problem
In ADR 0010, the system replaced Supabase Auth's shared mailer with a dedicated Gmail SMTP transport. While functional, standard Gmail SMTP transports with App Passwords encounter corporate deliverability challenges:
1. **Corporate Domain Alignment:** Sending corporate security communications from `@gmail.com` to `@iaclatam.com` addresses triggers spam filters, DMARC/SPF scrutiny, or quarantine policies.
2. **Microsoft 365 Tenant Sovereignty:** IAC Latam operates on Microsoft 365. Security policy dictates that enterprise transactional notifications originate from authentic tenant mailboxes (`pablo.reyes@iaclatam.com`) authenticated via Microsoft Entra ID (Azure AD).
3. **App Password Deprecation:** Modern corporate tenants disable legacy basic authentication (SMTP AUTH) in favor of OAuth 2.0 token-based authentication via Microsoft Entra ID.

## Decision

### 1. Microsoft Entra ID OAuth 2.0 Client Credentials Grant
- The backend acquires an application access token from Microsoft Entra ID using the OAuth 2.0 Client Credentials grant:
  - **Token URL:** `https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token`
  - **Scope:** `https://graph.microsoft.com/.default`
  - **Credentials:** `MS_CLIENT_ID` and `MS_CLIENT_SECRET`.
- The Azure App Registration requires the application-level permission `Mail.Send` with Administrator Consent.

### 2. Microsoft Graph SendMail Endpoint
- Emails are dispatched synchronously via the standard Graph API endpoint:
  - **URL:** `POST https://graph.microsoft.com/v1.0/users/{MAIL_SENDER}/sendMail`
  - **Sender Principal:** Strictly determined by `MAIL_SENDER` (e.g. `pablo.reyes@iaclatam.com`).
  - **Sender Display Name:** Configured via `MAIL_SENDER_NAME` (default: `AutoForm PDF - Seguridad`).
  - **Request Body:** JSON message with HTML template, recipient, and `saveToSentItems: false`.
  - **Success Response:** HTTP `202 Accepted`.

### 3. Preserved Architectural Guarantees
All core guarantees from ADR 0010 remain strictly enforced:
- **Blind Anti-Enumeration Defense:** `POST /api/auth/forgot-password` unconditionally returns HTTP 200 with generic feedback, regardless of email existence or mailer errors.
- **Relational Single-Use Cryptographic Tokens:** 32-byte URL-safe raw tokens with SHA-256 persistence in `password_reset_tokens`, 15-minute expiration, and strict single-use invalidation.
- **Dual-Auth Synchronization:** Supabase Auth is updated as the primary identity authority, followed by PostgreSQL `commercial_profiles.password_hash`.
- **Render Process Durability:** Email handoff executes synchronously with explicit network timeouts (10.0s).

### 4. Structured & Secure Telemetry (Render)
To enable zero-leakage operational observability on Render:
- `[RESET] provider=microsoft_graph`
- `[RESET] graph_configured=true|false (tenant=..., client_id=..., secret=..., sender=...)`
- `[RESET] email_sent=true`
- `[RESET] graph_send_failed: <ExceptionType>: <safe_sanitized_detail>`
- **Strict Data Sanitization:** Neither client secrets, access tokens, Authorization headers, raw reset links, nor unmasked email addresses are ever logged.

### 5. Multi-Provider Fallback & Local Simulation
- The active provider is controlled by `EMAIL_PROVIDER=microsoft_graph` (defaulting to `microsoft_graph` in production and staging).
- The existing SMTP transport remains available via `EMAIL_PROVIDER=smtp`.
- In local development (`APP_ENVIRONMENT=local`), if credentials are not configured, delivery is safely simulated to stdout with masked emails.

## Consequences

### Positive
- 100% deliverability from authoritative corporate domain (`@iaclatam.com`).
- Full compliance with modern Microsoft Entra ID enterprise security policies (no SMTP AUTH or App Passwords).
- Structured, leak-free telemetry for monitoring in Render logs.
- Preserved backward compatibility with local development and the existing test suite.

### Negative / Trade-offs
- Requires Azure App Registration with `Mail.Send` permission and Admin Consent in the Microsoft 365 tenant.
- Requires managing Entra ID client secret lifecycle and 180-day rotation.
