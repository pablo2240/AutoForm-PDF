# 0010: Backend-Authoritative Password Recovery, Dedicated Gmail SMTP Transport, and Consistent Dual-Auth Synchronization

Establish a zero-cost, high-reliability password recovery pipeline orchestrated authoritatively by FastAPI, backed by a dedicated Gmail SMTP transport with app-specific password, audited single-use tokens stored in PostgreSQL (`password_reset_tokens`), synchronous mail dispatch ensuring container durability, and consistent dual-auth credential synchronization with Supabase Auth as the primary authority.

## Context & Problem
Previously, password recovery in the frontend (`AuthPortal.tsx`) relied on `supabase.auth.resetPasswordForEmail()` via Supabase's default shared mailer (`mail.app.supabase.io`). This presented three operational barriers:
1. **Severe Rate Limiting & Deliverability Failure:** Supabase free tier enforces an hourly limit of 3–4 emails. Furthermore, corporate anti-spam systems for `@iaclatam.com` and `@iac.com.co` frequently quarantine or drop messages from shared Supabase infrastructure.
2. **Additional Cost Avoidance:** The organization requires a solution at $0 additional cost, without paying for third-party transactional tiers (e.g. paid SendGrid or Mailgun) or requiring modifications to corporate DNS records (Cloudflare / SPF / DKIM).
3. **Dual-Store Credential Desynchronization:** AutoForm PDF maintains identities across two systems: Supabase Auth (`auth.users`) and relational PostgreSQL (`commercial_profiles.password_hash`). If a user resets their password exclusively within Supabase Auth without synchronizing the local relational hash, fallback authentication endpoints (`/api/auth/login`) fail or accept obsolete credentials.

## Decision

### 1. Dedicated Gmail SMTP Transport ($0 Marginal Cost)
- Configure a dedicated system Google account (`SMTP_FROM_EMAIL=autoform.soporte@gmail.com`) using a 16-character App Password over STARTTLS (port 587) or SSL (port 465).
- Zero additional software subscriptions or corporate DNS alterations required.
- Remitente and credentials managed dynamically via environment variables (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME`).
- In local development (`APP_ENVIRONMENT=local`), if SMTP credentials are not configured, simulate delivery by printing the full reset URL to the server terminal.

### 2. Synchronous Process-Durable Email Dispatch
- Despatch the reset email **synchronously** within `POST /api/auth/forgot-password` with an explicit network timeout (5–8s).
- **Rationale against in-memory BackgroundTasks:** Container platforms (such as Render) frequently recycle worker processes upon idle timeouts or deployment events. Background tasks queued in memory can be permanently lost if the process recycles before SMTP handoff completes. A synchronous handoff with a user-facing "Enviando enlace..." state guarantees the message was accepted by Google SMTP before returning HTTP 200.
- **Blind Anti-Enumeration Defense:** The endpoint always returns an identical generic response (`"Si la dirección corresponde a un usuario corporativo registrado, hemos enviado las instrucciones de acceso."`) regardless of whether the email exists in the database.

### 3. Auditable Single-Use Relational Tokens (`password_reset_tokens`)
- Introduce a dedicated relational table `password_reset_tokens` in PostgreSQL / SQLite:
  ```sql
  CREATE TABLE password_reset_tokens (
      id VARCHAR(36) PRIMARY KEY,
      user_id VARCHAR(36) NOT NULL,
      token_hash VARCHAR(64) NOT NULL UNIQUE,
      expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
      used_at TIMESTAMP WITH TIME ZONE NULL,
      created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
      request_ip VARCHAR(45) NULL
  );
  CREATE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash);
  CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);
  ```
- **Cryptographic Security:** The client receives a high-entropy raw token (`secrets.token_urlsafe(32)`). Only its SHA-256 hash (`token_hash`) is persisted. Plaintext tokens are never stored.
- **Strict Expiration & Single Use:** Tokens strictly expire after 15 minutes (`expires_at`). Once consumed, `used_at` is stamped immediately. Reuse attempts are rejected with HTTP 400.
- **Early Verification Endpoint:** `GET /api/auth/verify-reset-token?token=...` enables the frontend to check token validity on view mount, warning the user immediately if the link has expired before they type a new password.

### 4. Consistent Dual-Auth Synchronization (Primary + Logged Retry)
- **Supabase Auth as Primary Authority:** In `POST /api/auth/reset-password`, the backend first updates Supabase Auth using the administrative client:
  ```python
  admin_client.auth.admin.update_user_by_id(user.id, {"password": new_password})
  ```
- **Relational Hash Synchronization:** Upon Supabase Auth success, `commercial_profiles.password_hash` is updated with `hash_password(new_password)`.
- **Fault Tolerance & Telemetry:** Because true 2-phase commit (2PC) is impossible across distinct cloud systems, if Supabase succeeds but local relational persistence fails, the token is marked as consumed, the incident is logged with high-severity telemetry (`[CREDENTIAL_SYNC_ERROR]`), and the profile is flagged (`needs_password_hash_sync = True`) so subsequent authenticated requests or logins repair the projection. Obsolete passwords are never accepted.

## Consequences

### Positive
- Reliable, inbox-delivered emails without hitting Supabase free-tier throttling.
- Zero financial cost ($0/month) and zero dependency on corporate DNS management.
- Complete protection against container recycling message loss during Render restarts.
- Elimination of credential divergence between Supabase Auth and PostgreSQL.
- Anti-enumeration defense protecting corporate user lists from discovery.

### Negative / Trade-offs
- Requires generating and running an Alembic migration for `password_reset_tokens`.
- Requires creating a dedicated Google account and 16-character App Password.
- User waits 1–3 seconds during "Olvidé mi contraseña" while Google SMTP acknowledges receipt.
