-- ==============================================================================
-- AutoForm PDF (SmartFormAI) - Incident Remediation & Full Canonical Schema Restoration
-- Migration: 20260918190000_restore_pdf_schema_after_cross_project_incident.sql
-- Target: tnhedxwbpqihlqbtzudt (AutoForm PDF Producción)
-- Scope: Revert cross-project AutoForm Excel deployment and fully restore canonical PDF schema
-- Security: Preserves migration history in supabase_migrations.schema_migrations
-- ==============================================================================

-- ==============================================================================
-- Phase 1: Remanentes de AutoForm Excel Cleanup (CASCADE Safe Dropping)
-- ==============================================================================
DROP TRIGGER IF EXISTS trigger_validar_dominio_correo ON auth.users;
DROP FUNCTION IF EXISTS public.validar_dominio_correo_auth() CASCADE;
DROP TABLE IF EXISTS public.operadores CASCADE;
DROP TABLE IF EXISTS public.perfiles_usuario CASCADE;
DROP TABLE IF EXISTS public.perfiles_empresa CASCADE;
DROP TABLE IF EXISTS public.migration_runs CASCADE;
DROP FUNCTION IF EXISTS public.is_active_user() CASCADE;
DROP FUNCTION IF EXISTS public.proteger_columnas_perfil_usuario() CASCADE;
DROP FUNCTION IF EXISTS public.actualizar_timestamp_updated_at() CASCADE;

-- ==============================================================================
-- Phase 2: Extensions
-- ==============================================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- Phase 3: Core Tables Schema (Canonical AutoForm PDF)
-- ==============================================================================

-- 1. Companies
CREATE TABLE IF NOT EXISTS public.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    razon_social VARCHAR NOT NULL,
    nombre_comercial VARCHAR,
    nit VARCHAR NOT NULL UNIQUE,
    dv VARCHAR NOT NULL CHECK (dv ~ '^[0-9]{1,2}$'),
    pais VARCHAR NOT NULL DEFAULT 'Colombia',
    departamento VARCHAR,
    ciudad VARCHAR,
    direccion_principal TEXT,
    telefono VARCHAR,
    pagina_web VARCHAR,
    total_activos NUMERIC,
    total_pasivos NUMERIC,
    total_patrimonio NUMERIC,
    total_ingresos_mensuales NUMERIC,
    total_egresos_mensuales NUMERIC,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    migration_batch_id UUID
);
CREATE INDEX IF NOT EXISTS idx_companies_batch ON public.companies USING btree (migration_batch_id);

-- 2. Profiles
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    email VARCHAR NOT NULL,
    nombre VARCHAR NOT NULL CHECK (char_length(TRIM(BOTH FROM nombre)) >= 2),
    apellido VARCHAR NOT NULL CHECK (char_length(TRIM(BOTH FROM apellido)) >= 2),
    display_name VARCHAR NOT NULL,
    cargo VARCHAR NOT NULL CHECK (char_length(TRIM(BOTH FROM cargo)) >= 2),
    celular VARCHAR NOT NULL,
    tipo_documento VARCHAR NOT NULL DEFAULT 'C.C',
    documento_identidad VARCHAR,
    role VARCHAR NOT NULL DEFAULT 'commercial' CHECK (role IN ('admin', 'commercial')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    migration_batch_id UUID,
    CONSTRAINT chk_profiles_corporate_email CHECK (lower(email::text) ~* '^[^@\s]+@(iaclatam\.com|iac\.com\.co)$')
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_profiles_email_lower ON public.profiles USING btree (lower(email::text));
CREATE INDEX IF NOT EXISTS idx_profiles_company ON public.profiles USING btree (company_id);
CREATE INDEX IF NOT EXISTS idx_profiles_batch ON public.profiles USING btree (migration_batch_id);

-- 3. Company Bank Accounts
CREATE TABLE IF NOT EXISTS public.company_bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    entidad_bancaria VARCHAR NOT NULL,
    tipo_cuenta VARCHAR NOT NULL CHECK (tipo_cuenta IN ('Ahorros', 'Corriente')),
    numero_cuenta VARCHAR NOT NULL,
    es_principal BOOLEAN NOT NULL DEFAULT false,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    migration_batch_id UUID
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_principal_bank_account ON public.company_bank_accounts (company_id) WHERE (es_principal = true AND activo = true);
CREATE INDEX IF NOT EXISTS idx_bank_accounts_company ON public.company_bank_accounts USING btree (company_id);
CREATE INDEX IF NOT EXISTS idx_bank_accounts_batch ON public.company_bank_accounts USING btree (migration_batch_id);

-- 4. Legal Representatives
CREATE TABLE IF NOT EXISTS public.legal_representatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    nombre_completo VARCHAR NOT NULL,
    nombres VARCHAR NOT NULL,
    apellidos VARCHAR NOT NULL,
    tipo_documento VARCHAR NOT NULL DEFAULT 'C.C',
    numero_documento VARCHAR NOT NULL,
    lugar_expedicion VARCHAR,
    fecha_expedicion DATE,
    email VARCHAR,
    celular VARCHAR,
    firma_storage_path VARCHAR,
    es_principal BOOLEAN NOT NULL DEFAULT true,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    migration_batch_id UUID
);
CREATE INDEX IF NOT EXISTS idx_legal_rep_company ON public.legal_representatives USING btree (company_id);
CREATE INDEX IF NOT EXISTS idx_legal_rep_batch ON public.legal_representatives USING btree (migration_batch_id);

-- 5. PDF Templates
CREATE TABLE IF NOT EXISTS public.pdf_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    codigo VARCHAR NOT NULL,
    nombre VARCHAR NOT NULL,
    descripcion TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    migration_batch_id UUID,
    CONSTRAINT uq_pdf_templates_company_codigo UNIQUE (company_id, codigo)
);
CREATE INDEX IF NOT EXISTS idx_pdf_templates_company ON public.pdf_templates USING btree (company_id);
CREATE INDEX IF NOT EXISTS idx_pdf_templates_batch ON public.pdf_templates USING btree (migration_batch_id);

-- 6. PDF Template Versions
CREATE TABLE IF NOT EXISTS public.pdf_template_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES public.pdf_templates(id) ON DELETE CASCADE,
    version INT NOT NULL CHECK (version >= 1),
    filename VARCHAR NOT NULL,
    storage_path VARCHAR NOT NULL,
    page_count INT NOT NULL CHECK (page_count >= 1),
    is_acroform BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'retired')),
    migration_batch_id UUID,
    CONSTRAINT uq_template_version UNIQUE (template_id, version)
);
CREATE INDEX IF NOT EXISTS idx_template_versions_template ON public.pdf_template_versions USING btree (template_id);
CREATE INDEX IF NOT EXISTS idx_pdf_versions_batch ON public.pdf_template_versions USING btree (migration_batch_id);

-- 7. PDF Mappings
CREATE TABLE IF NOT EXISTS public.pdf_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_version_id UUID NOT NULL REFERENCES public.pdf_template_versions(id) ON DELETE CASCADE,
    field_key VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    source_path VARCHAR NOT NULL,
    page_index INT NOT NULL CHECK (page_index >= 0),
    coordinates JSONB,
    field_type VARCHAR NOT NULL DEFAULT 'text',
    validation_rules JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    migration_batch_id UUID
);
CREATE INDEX IF NOT EXISTS idx_pdf_mappings_version ON public.pdf_mappings USING btree (template_version_id);
CREATE INDEX IF NOT EXISTS idx_pdf_mappings_batch ON public.pdf_mappings USING btree (migration_batch_id);

-- 8. Form Fill History
CREATE TABLE IF NOT EXISTS public.form_fill_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    template_version_id UUID NOT NULL REFERENCES public.pdf_template_versions(id) ON DELETE RESTRICT,
    operator_user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    commercial_profile_id UUID REFERENCES public.profiles(id) ON DELETE RESTRICT,
    status VARCHAR NOT NULL CHECK (status IN ('draft', 'processing', 'completed', 'failed')),
    output_storage_path VARCHAR,
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_completed_has_output CHECK (status <> 'completed' OR output_storage_path IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_history_company ON public.form_fill_history USING btree (company_id);
CREATE INDEX IF NOT EXISTS idx_history_operator ON public.form_fill_history USING btree (operator_user_id);
CREATE INDEX IF NOT EXISTS idx_history_version ON public.form_fill_history USING btree (template_version_id);

-- 9. Migration Runs
CREATE TABLE IF NOT EXISTS public.migration_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL UNIQUE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status VARCHAR NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'rolled_back', 'failed')),
    target_project_ref VARCHAR NOT NULL,
    manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_migration_runs_batch ON public.migration_runs USING btree (batch_id);

-- ==============================================================================
-- Phase 4: Stored Procedures and Helper Functions (18 Canonical Functions)
-- ==============================================================================

-- Function: set_updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$function$;

-- Function: get_user_company_id
CREATE OR REPLACE FUNCTION public.get_user_company_id()
 RETURNS uuid
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
    SELECT company_id 
    FROM public.profiles 
    WHERE id = auth.uid() 
      AND is_active = true;
$function$;

-- Function: is_admin
CREATE OR REPLACE FUNCTION public.is_admin()
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
    SELECT EXISTS (
        SELECT 1 
        FROM public.profiles 
        WHERE id = auth.uid() 
          AND role = 'admin' 
          AND is_active = true
    );
$function$;

-- Function: get_company_commercial_profiles
CREATE OR REPLACE FUNCTION public.get_company_commercial_profiles()
 RETURNS TABLE(id uuid, company_id uuid, display_name character varying, cargo character varying, email character varying, celular character varying, is_active boolean)
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
    v_company_id UUID;
BEGIN
    v_company_id := public.get_user_company_id();
    IF v_company_id IS NULL THEN
        RETURN;
    END IF;

    RETURN QUERY
    SELECT 
        p.id,
        p.company_id,
        p.display_name,
        p.cargo,
        p.email,
        p.celular,
        p.is_active
    FROM public.profiles p
    WHERE p.company_id = v_company_id
      AND p.is_active = true
    ORDER BY p.display_name ASC;
END;
$function$;

-- Function: check_profile_column_security
CREATE OR REPLACE FUNCTION public.check_profile_column_security()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
BEGIN
    -- If user is updating their own record and is NOT an admin:
    IF auth.uid() = NEW.id AND NOT public.is_admin() THEN
        IF NEW.company_id IS DISTINCT FROM OLD.company_id THEN
            RAISE EXCEPTION 'Unauthorized: Non-admin users cannot change company_id';
        END IF;
        IF NEW.role IS DISTINCT FROM OLD.role THEN
            RAISE EXCEPTION 'Unauthorized: Non-admin users cannot change role';
        END IF;
        IF NEW.is_active IS DISTINCT FROM OLD.is_active THEN
            RAISE EXCEPTION 'Unauthorized: Non-admin users cannot change is_active';
        END IF;
        IF NEW.email IS DISTINCT FROM OLD.email THEN
            RAISE EXCEPTION 'Unauthorized: Non-admin users cannot change email';
        END IF;
        IF NEW.documento_identidad IS DISTINCT FROM OLD.documento_identidad THEN
            RAISE EXCEPTION 'Unauthorized: Non-admin users cannot change documento_identidad';
        END IF;
        IF NEW.tipo_documento IS DISTINCT FROM OLD.tipo_documento THEN
            RAISE EXCEPTION 'Unauthorized: Non-admin users cannot change tipo_documento';
        END IF;
        IF NEW.cargo IS DISTINCT FROM OLD.cargo THEN
            RAISE EXCEPTION 'Unauthorized: Non-admin users cannot change cargo';
        END IF;
    END IF;
    RETURN NEW;
END;
$function$;

-- Function: check_legal_rep_company_isolation
CREATE OR REPLACE FUNCTION public.check_legal_rep_company_isolation()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
BEGIN
    IF NEW.user_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.profiles 
            WHERE id = NEW.user_id AND company_id = NEW.company_id
        ) THEN
            RAISE EXCEPTION 'Cross-company violation: user_id % does not belong to company %', NEW.user_id, NEW.company_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$function$;

-- Function: check_form_fill_history_isolation
CREATE OR REPLACE FUNCTION public.check_form_fill_history_isolation()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.profiles 
        WHERE id = NEW.operator_user_id AND company_id = NEW.company_id
    ) THEN
        RAISE EXCEPTION 'Cross-company violation: operator_user_id % does not belong to company %', NEW.operator_user_id, NEW.company_id;
    END IF;

    IF NEW.commercial_profile_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.profiles 
            WHERE id = NEW.commercial_profile_id AND company_id = NEW.company_id
        ) THEN
            RAISE EXCEPTION 'Cross-company violation: commercial_profile_id % does not belong to company %', NEW.commercial_profile_id, NEW.company_id;
        END IF;
    END IF;

    IF NOT EXISTS (
        SELECT 1 
        FROM public.pdf_template_versions v
        JOIN public.pdf_templates t ON v.template_id = t.id
        WHERE v.id = NEW.template_version_id AND t.company_id = NEW.company_id
    ) THEN
        RAISE EXCEPTION 'Cross-company violation: template_version_id % does not belong to company %', NEW.template_version_id, NEW.company_id;
    END IF;

    RETURN NEW;
END;
$function$;

-- Function: check_pdf_mappings_lifecycle
CREATE OR REPLACE FUNCTION public.check_pdf_mappings_lifecycle()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
    v_ver_id UUID;
    v_ver_status VARCHAR(20);
BEGIN
    v_ver_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.template_version_id ELSE NEW.template_version_id END;

    SELECT status INTO v_ver_status
    FROM public.pdf_template_versions
    WHERE id = v_ver_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Template version % not found.', v_ver_id;
    END IF;

    IF v_ver_status != 'draft' THEN
        RAISE EXCEPTION 'Cannot modify mappings: template version % is in % status. Mappings can only be modified in draft status.', v_ver_id, v_ver_status;
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.form_fill_history 
        WHERE template_version_id = v_ver_id
    ) THEN
        RAISE EXCEPTION 'Cannot modify mappings for template version % because it has associated form fill history. Create a new template version instead.', v_ver_id;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$function$;

-- Function: prevent_template_version_mutation
CREATE OR REPLACE FUNCTION public.prevent_template_version_mutation()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.id::text NOT LIKE '00000000-0000-0000-0000-%' AND OLD.migration_batch_id IS NULL THEN
            RAISE EXCEPTION 'Template versions are immutable: DELETE is prohibited.';
        END IF;
        RETURN OLD;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF NEW.id != OLD.id 
           OR NEW.template_id != OLD.template_id 
           OR NEW.version != OLD.version 
           OR NEW.filename != OLD.filename 
           OR NEW.storage_path != OLD.storage_path 
           OR NEW.page_count != OLD.page_count 
           OR NEW.is_acroform != OLD.is_acroform 
           OR NEW.created_by IS DISTINCT FROM OLD.created_by 
           OR NEW.created_at != OLD.created_at THEN
            RAISE EXCEPTION 'Template version details are immutable. Only status transitions are permitted.';
        END IF;

        IF OLD.status = 'draft' AND NEW.status = 'published' THEN
            RETURN NEW;
        END IF;

        IF OLD.status = 'published' AND NEW.status = 'archived' THEN
            RETURN NEW;
        END IF;

        IF OLD.status = NEW.status THEN
            RETURN NEW;
        END IF;

        RAISE EXCEPTION 'Invalid status transition from % to %', OLD.status, NEW.status;
    END IF;

    RETURN NEW;
END;
$function$;

-- Function: prevent_historical_mappings_mutation
CREATE OR REPLACE FUNCTION public.prevent_historical_mappings_mutation()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
    v_ver_id UUID;
BEGIN
    v_ver_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.template_version_id ELSE NEW.template_version_id END;
    
    IF EXISTS (
        SELECT 1 FROM public.form_fill_history 
        WHERE template_version_id = v_ver_id
    ) THEN
        RAISE EXCEPTION 'Cannot modify or delete mappings for template version % because it has associated form fill history. Create a new template version instead.', v_ver_id;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$function$;

-- Function: prevent_form_fill_history_mutation
CREATE OR REPLACE FUNCTION public.prevent_form_fill_history_mutation()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
BEGIN
    IF TG_OP = 'DELETE' THEN
        -- Only synthetic test companies (UUID prefix 00000000-0000-0000-0000-) are permitted to be purged in tests/teardown
        IF OLD.company_id::text NOT LIKE '00000000-0000-0000-0000-%' THEN
            RAISE EXCEPTION 'form_fill_history records are audit logs and cannot be deleted';
        END IF;
        RETURN OLD;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF OLD.status IN ('completed', 'failed') THEN
            RAISE EXCEPTION 'form_fill_history record % is in terminal state % and cannot be modified', OLD.id, OLD.status;
        END IF;

        IF NEW.id != OLD.id 
           OR NEW.company_id != OLD.company_id 
           OR NEW.template_version_id != OLD.template_version_id 
           OR NEW.operator_user_id != OLD.operator_user_id 
           OR NEW.commercial_profile_id IS DISTINCT FROM OLD.commercial_profile_id 
           OR NEW.created_at != OLD.created_at THEN
            RAISE EXCEPTION 'Core form_fill_history attributes cannot be modified.';
        END IF;
    END IF;

    RETURN NEW;
END;
$function$;

-- Function: publish_template_version
CREATE OR REPLACE FUNCTION public.publish_template_version(p_version_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
    v_user_company_id UUID;
    v_version_company_id UUID;
    v_current_status VARCHAR(20);
BEGIN
    IF NOT public.is_admin() THEN
        RAISE EXCEPTION 'Access denied: only administrators can publish template versions.';
    END IF;

    v_user_company_id := public.get_user_company_id();
    IF v_user_company_id IS NULL THEN
        RAISE EXCEPTION 'Access denied: active company profile not found.';
    END IF;

    SELECT t.company_id, v.status 
    INTO v_version_company_id, v_current_status
    FROM public.pdf_template_versions v
    JOIN public.pdf_templates t ON v.template_id = t.id
    WHERE v.id = p_version_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Template version % not found.', p_version_id;
    END IF;

    IF v_version_company_id != v_user_company_id THEN
        RAISE EXCEPTION 'Access denied: cross-company template modification is prohibited.';
    END IF;

    IF v_current_status != 'draft' THEN
        RAISE EXCEPTION 'Only versions in draft status can be published. Current status is %.', v_current_status;
    END IF;

    UPDATE public.pdf_template_versions
    SET status = 'published'
    WHERE id = p_version_id;
END;
$function$;

-- Function: retire_template_version
CREATE OR REPLACE FUNCTION public.retire_template_version(p_version_id uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
    v_user_company_id UUID;
    v_version_company_id UUID;
    v_current_status VARCHAR(20);
BEGIN
    IF NOT public.is_admin() THEN
        RAISE EXCEPTION 'Access denied: only administrators can retire template versions.';
    END IF;

    v_user_company_id := public.get_user_company_id();
    IF v_user_company_id IS NULL THEN
        RAISE EXCEPTION 'Access denied: active company profile not found.';
    END IF;

    SELECT t.company_id, v.status 
    INTO v_version_company_id, v_current_status
    FROM public.pdf_template_versions v
    JOIN public.pdf_templates t ON v.template_id = t.id
    WHERE v.id = p_version_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Template version % not found.', p_version_id;
    END IF;

    IF v_version_company_id != v_user_company_id THEN
        RAISE EXCEPTION 'Access denied: cross-company template modification is prohibited.';
    END IF;

    IF v_current_status != 'published' THEN
        RAISE EXCEPTION 'Only published versions can be retired. Current status is %.', v_current_status;
    END IF;

    UPDATE public.pdf_template_versions
    SET status = 'retired'
    WHERE id = p_version_id;
END;
$function$;

-- Function: start_form_fill
CREATE OR REPLACE FUNCTION public.start_form_fill(p_template_version_id uuid, p_commercial_profile_id uuid DEFAULT NULL::uuid, p_metadata jsonb DEFAULT NULL::jsonb)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
    v_user_id UUID := auth.uid();
    v_company_id UUID := public.get_user_company_id();
    v_ver_company_id UUID;
    v_ver_status VARCHAR(20);
    v_history_id UUID;
BEGIN
    IF v_user_id IS NULL OR v_company_id IS NULL THEN
        RAISE EXCEPTION 'Authentication required: active session not found.';
    END IF;

    SELECT t.company_id, v.status
    INTO v_ver_company_id, v_ver_status
    FROM public.pdf_template_versions v
    JOIN public.pdf_templates t ON v.template_id = t.id
    WHERE v.id = p_template_version_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Template version % not found.', p_template_version_id;
    END IF;

    IF v_ver_company_id != v_company_id THEN
        RAISE EXCEPTION 'Cross-company violation: template version % does not belong to company %', p_template_version_id, v_company_id;
    END IF;

    IF v_ver_status != 'published' THEN
        RAISE EXCEPTION 'Cannot start form fill: template version % is in % status. Only published versions can be filled.', p_template_version_id, v_ver_status;
    END IF;

    IF p_commercial_profile_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.profiles
            WHERE id = p_commercial_profile_id AND company_id = v_company_id AND is_active = true
        ) THEN
            RAISE EXCEPTION 'Commercial profile % does not exist or is inactive in company %', p_commercial_profile_id, v_company_id;
        END IF;
    END IF;

    INSERT INTO public.form_fill_history (
        company_id,
        template_version_id,
        operator_user_id,
        commercial_profile_id,
        status,
        metadata
    ) VALUES (
        v_company_id,
        p_template_version_id,
        v_user_id,
        p_commercial_profile_id,
        'processing',
        p_metadata
    ) RETURNING id INTO v_history_id;

    RETURN v_history_id;
END;
$function$;

-- Function: complete_form_fill
CREATE OR REPLACE FUNCTION public.complete_form_fill(p_history_id uuid, p_output_storage_path text, p_metadata jsonb DEFAULT NULL::jsonb)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
    v_user_id UUID := auth.uid();
    v_company_id UUID := public.get_user_company_id();
    v_hist_company_id UUID;
    v_hist_operator_id UUID;
    v_hist_status VARCHAR(50);
    v_expected_path TEXT;
BEGIN
    IF v_user_id IS NULL OR v_company_id IS NULL THEN
        RAISE EXCEPTION 'Authentication required: active session not found.';
    END IF;

    SELECT company_id, operator_user_id, status
    INTO v_hist_company_id, v_hist_operator_id, v_hist_status
    FROM public.form_fill_history
    WHERE id = p_history_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Form fill history % not found.', p_history_id;
    END IF;

    IF v_hist_company_id != v_company_id OR v_hist_operator_id != v_user_id THEN
        RAISE EXCEPTION 'Access denied: not authorized to complete form fill %', p_history_id;
    END IF;

    IF v_hist_status != 'processing' THEN
        RAISE EXCEPTION 'Invalid state transition: cannot complete form fill % with current status %', p_history_id, v_hist_status;
    END IF;

    IF p_output_storage_path IS NULL OR TRIM(p_output_storage_path) = '' THEN
        RAISE EXCEPTION 'output_storage_path cannot be empty on completion';
    END IF;

    v_expected_path := v_company_id::text || '/' || v_user_id::text || '/' || p_history_id::text || '.pdf';
    IF p_output_storage_path != v_expected_path THEN
        RAISE EXCEPTION 'Invalid output storage path %. Expected strictly: %', p_output_storage_path, v_expected_path;
    END IF;

    UPDATE public.form_fill_history
    SET status = 'completed',
        output_storage_path = p_output_storage_path,
        metadata = CASE WHEN p_metadata IS NOT NULL THEN COALESCE(metadata, '{}'::jsonb) || p_metadata ELSE metadata END
    WHERE id = p_history_id;
END;
$function$;

-- Function: fail_form_fill
CREATE OR REPLACE FUNCTION public.fail_form_fill(p_history_id uuid, p_error_message text, p_metadata jsonb DEFAULT NULL::jsonb)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
    v_user_id UUID := auth.uid();
    v_company_id UUID := public.get_user_company_id();
    v_hist_company_id UUID;
    v_hist_operator_id UUID;
    v_hist_status VARCHAR(50);
BEGIN
    IF v_user_id IS NULL OR v_company_id IS NULL THEN
        RAISE EXCEPTION 'Authentication required: active session not found.';
    END IF;

    SELECT company_id, operator_user_id, status
    INTO v_hist_company_id, v_hist_operator_id, v_hist_status
    FROM public.form_fill_history
    WHERE id = p_history_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Form fill history % not found.', p_history_id;
    END IF;

    IF v_hist_company_id != v_company_id OR v_hist_operator_id != v_user_id THEN
        RAISE EXCEPTION 'Access denied: not authorized to fail form fill %', p_history_id;
    END IF;

    IF v_hist_status != 'processing' THEN
        RAISE EXCEPTION 'Invalid state transition: cannot fail form fill % with current status %', p_history_id, v_hist_status;
    END IF;

    IF p_error_message IS NULL OR TRIM(p_error_message) = '' THEN
        RAISE EXCEPTION 'error_message is required when reporting form fill failure';
    END IF;

    UPDATE public.form_fill_history
    SET status = 'failed',
        error_message = TRIM(p_error_message),
        metadata = CASE WHEN p_metadata IS NOT NULL THEN COALESCE(metadata, '{}'::jsonb) || p_metadata ELSE metadata END
    WHERE id = p_history_id;
END;
$function$;

-- Function: handle_new_user
CREATE OR REPLACE FUNCTION public.handle_new_user()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
    v_company_id UUID;
    v_nombre VARCHAR(100);
    v_apellido VARCHAR(100);
    v_cargo VARCHAR(100);
    v_celular VARCHAR(50);
    v_role VARCHAR(30);
    v_tipo_doc VARCHAR(20);
    v_doc_id VARCHAR(50);
    v_batch_id UUID;
    v_existing_profile RECORD;
BEGIN
    -- 1. Consultar si ya existe perfil para el usuario
    SELECT * INTO v_existing_profile FROM public.profiles WHERE id = NEW.id;

    -- Extraer migration_batch_id si fue configurado en app_metadata
    IF NEW.raw_app_meta_data->>'migration_batch_id' IS NOT NULL THEN
        BEGIN
            v_batch_id := (NEW.raw_app_meta_data->>'migration_batch_id')::UUID;
        EXCEPTION WHEN OTHERS THEN
            v_batch_id := NULL;
        END;
    END IF;

    -- 2. Extraer y validar company_id: estrictamente desde raw_app_meta_data (server-side)
    IF NEW.raw_app_meta_data->>'company_id' IS NOT NULL THEN
        BEGIN
            v_company_id := (NEW.raw_app_meta_data->>'company_id')::UUID;
        EXCEPTION WHEN OTHERS THEN
            RAISE EXCEPTION 'Cannot register/update user: invalid UUID for company_id in app_metadata';
        END;

        IF NOT EXISTS (SELECT 1 FROM public.companies WHERE id = v_company_id AND is_active = true) THEN
            RAISE EXCEPTION 'Cannot register/update user: target company does not exist or is inactive';
        END IF;
    ELSIF v_existing_profile.id IS NOT NULL THEN
        v_company_id := v_existing_profile.company_id;
    ELSE
        -- Si aún no hay company_id en app_metadata (fase intermedia de GoTrue), esperar a que GoTrue complete app_metadata
        RETURN NEW;
    END IF;

    -- 3. Validar dominio corporativo autorizado
    IF NOT (LOWER(NEW.email) ~* '^[^@\s]+@(iaclatam\.com|iac\.com\.co)$') THEN
        RAISE EXCEPTION 'Cannot register/update user: email domain % is not authorized', NEW.email;
    END IF;

    -- 4. Extraer role: estrictamente desde raw_app_meta_data (ignorar user_metadata)
    IF NEW.raw_app_meta_data->>'role' IS NOT NULL THEN
        v_role := LOWER(NEW.raw_app_meta_data->>'role');
        IF v_role NOT IN ('admin', 'commercial') THEN
            RAISE EXCEPTION 'Cannot register/update user: invalid role % in app_metadata', v_role;
        END IF;
    ELSIF v_existing_profile.id IS NOT NULL THEN
        v_role := v_existing_profile.role;
    ELSE
        v_role := 'commercial';
    END IF;

    -- 5. Extraer atributos permitidos desde metadatos
    -- Atributos editables por el usuario (sincronizan desde raw_user_meta_data):
    v_nombre := TRIM(COALESCE(NEW.raw_user_meta_data->>'nombre', ''));
    v_apellido := TRIM(COALESCE(NEW.raw_user_meta_data->>'apellido', ''));
    v_celular := TRIM(COALESCE(NEW.raw_user_meta_data->>'celular', ''));

    -- Atributos administrativos protegidos (cargo, documento_identidad, tipo_documento):
    -- On INSERT: admin may set them in app_metadata or user_metadata.
    -- On UPDATE: only raw_app_meta_data is accepted; raw_user_meta_data is STRICTLY IGNORED.
    IF v_existing_profile.id IS NULL THEN
        v_cargo := TRIM(COALESCE(NEW.raw_app_meta_data->>'cargo', NEW.raw_user_meta_data->>'cargo', ''));
        v_tipo_doc := COALESCE(NEW.raw_app_meta_data->>'tipo_documento', NEW.raw_user_meta_data->>'tipo_documento', 'C.C');
        v_doc_id := COALESCE(NEW.raw_app_meta_data->>'documento_identidad', NEW.raw_user_meta_data->>'documento_identidad');

        IF char_length(v_nombre) < 2 OR char_length(v_apellido) < 2 OR char_length(v_cargo) < 2 OR char_length(v_celular) < 5 THEN
            IF TG_OP = 'INSERT' AND NEW.raw_app_meta_data->>'company_id' IS NULL THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'Cannot register user: missing or invalid profile attributes (nombre, apellido, cargo, celular)';
        END IF;
    ELSE
        -- In UPDATE: cargo and doc ID change ONLY if provided in raw_app_meta_data (admin operation)
        v_cargo := TRIM(COALESCE(NEW.raw_app_meta_data->>'cargo', v_existing_profile.cargo, ''));
        v_tipo_doc := COALESCE(NEW.raw_app_meta_data->>'tipo_documento', v_existing_profile.tipo_documento, 'C.C');
        v_doc_id := COALESCE(NEW.raw_app_meta_data->>'documento_identidad', v_existing_profile.documento_identidad);
    END IF;

    -- 6. Inserción o actualización idempotente
    INSERT INTO public.profiles (
        id,
        company_id,
        email,
        nombre,
        apellido,
        display_name,
        cargo,
        celular,
        tipo_documento,
        documento_identidad,
        role,
        is_active,
        migration_batch_id,
        created_at,
        updated_at
    ) VALUES (
        NEW.id,
        v_company_id,
        LOWER(NEW.email),
        v_nombre,
        v_apellido,
        TRIM(v_nombre || ' ' || v_apellido),
        v_cargo,
        v_celular,
        v_tipo_doc,
        v_doc_id,
        v_role,
        true,
        v_batch_id,
        NOW(),
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        company_id = COALESCE(v_company_id, public.profiles.company_id),
        role = COALESCE(v_role, public.profiles.role),
        email = LOWER(NEW.email),
        migration_batch_id = COALESCE(v_batch_id, public.profiles.migration_batch_id),
        nombre = CASE WHEN char_length(v_nombre) >= 2 THEN v_nombre ELSE public.profiles.nombre END,
        apellido = CASE WHEN char_length(v_apellido) >= 2 THEN v_apellido ELSE public.profiles.apellido END,
        display_name = CASE 
            WHEN char_length(v_nombre) >= 2 AND char_length(v_apellido) >= 2 THEN TRIM(v_nombre || ' ' || v_apellido)
            WHEN char_length(v_nombre) >= 2 THEN TRIM(v_nombre || ' ' || public.profiles.apellido)
            WHEN char_length(v_apellido) >= 2 THEN TRIM(public.profiles.nombre || ' ' || v_apellido)
            ELSE public.profiles.display_name
        END,
        -- CRITICAL: cargo, documento_identidad, tipo_documento only change if v_cargo / v_doc_id came from raw_app_meta_data
        cargo = CASE 
            WHEN NEW.raw_app_meta_data->>'cargo' IS NOT NULL AND char_length(TRIM(NEW.raw_app_meta_data->>'cargo')) >= 2 
            THEN TRIM(NEW.raw_app_meta_data->>'cargo')
            ELSE public.profiles.cargo 
        END,
        celular = CASE WHEN char_length(v_celular) >= 5 THEN v_celular ELSE public.profiles.celular END,
        tipo_documento = CASE 
            WHEN NEW.raw_app_meta_data->>'tipo_documento' IS NOT NULL 
            THEN NEW.raw_app_meta_data->>'tipo_documento'
            ELSE public.profiles.tipo_documento 
        END,
        documento_identidad = CASE 
            WHEN NEW.raw_app_meta_data->>'documento_identidad' IS NOT NULL 
            THEN NEW.raw_app_meta_data->>'documento_identidad'
            ELSE public.profiles.documento_identidad 
        END,
        updated_at = NOW();

    RETURN NEW;
END;
$function$;

-- Function: rollback_migration_batch
CREATE OR REPLACE FUNCTION public.rollback_migration_batch(p_batch_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
    v_run RECORD;
    v_deleted_counts JSONB := '{}'::jsonb;
    v_count INTEGER;
BEGIN
    -- 1. Check if migration run exists
    SELECT * INTO v_run FROM public.migration_runs WHERE batch_id = p_batch_id;
    IF v_run.batch_id IS NULL THEN
        RAISE EXCEPTION 'Migration run with batch_id % not found', p_batch_id;
    END IF;

    IF v_run.status = 'rolled_back' THEN
        RAISE EXCEPTION 'Migration batch % has already been rolled back', p_batch_id;
    END IF;

    -- 2. Audit safety check: ensure no form_fill_history exists referencing templates, profiles, or company of this batch
    IF EXISTS (
        SELECT 1 FROM public.form_fill_history h
        WHERE h.template_version_id IN (
            SELECT v.id FROM public.pdf_template_versions v WHERE v.migration_batch_id = p_batch_id
        )
        OR h.operator_user_id IN (
            SELECT p.id FROM public.profiles p WHERE p.migration_batch_id = p_batch_id
        )
        OR h.commercial_profile_id IN (
            SELECT p.id FROM public.profiles p WHERE p.migration_batch_id = p_batch_id
        )
        OR h.company_id IN (
            SELECT c.id FROM public.companies c WHERE c.migration_batch_id = p_batch_id
        )
    ) THEN
        RAISE EXCEPTION 'Cannot rollback batch %: audit records exist in form_fill_history referencing this batch', p_batch_id;
    END IF;

    -- 3. Delete in reverse dependency order:
    -- pdf_mappings
    DELETE FROM public.pdf_mappings
    WHERE migration_batch_id = p_batch_id
       OR template_version_id IN (SELECT id FROM public.pdf_template_versions WHERE migration_batch_id = p_batch_id);
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_deleted_counts := jsonb_set(v_deleted_counts, '{pdf_mappings}', to_jsonb(v_count));

    -- pdf_template_versions
    DELETE FROM public.pdf_template_versions WHERE migration_batch_id = p_batch_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_deleted_counts := jsonb_set(v_deleted_counts, '{pdf_template_versions}', to_jsonb(v_count));

    -- pdf_templates
    DELETE FROM public.pdf_templates WHERE migration_batch_id = p_batch_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_deleted_counts := jsonb_set(v_deleted_counts, '{pdf_templates}', to_jsonb(v_count));

    -- legal_representatives
    DELETE FROM public.legal_representatives WHERE migration_batch_id = p_batch_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_deleted_counts := jsonb_set(v_deleted_counts, '{legal_representatives}', to_jsonb(v_count));

    -- company_bank_accounts
    DELETE FROM public.company_bank_accounts WHERE migration_batch_id = p_batch_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_deleted_counts := jsonb_set(v_deleted_counts, '{company_bank_accounts}', to_jsonb(v_count));

    -- profiles
    DELETE FROM public.profiles WHERE migration_batch_id = p_batch_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_deleted_counts := jsonb_set(v_deleted_counts, '{profiles}', to_jsonb(v_count));

    -- companies
    DELETE FROM public.companies WHERE migration_batch_id = p_batch_id;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    v_deleted_counts := jsonb_set(v_deleted_counts, '{companies}', to_jsonb(v_count));

    -- Update migration run status
    UPDATE public.migration_runs
    SET status = 'rolled_back',
        completed_at = now()
    WHERE batch_id = p_batch_id;

    RETURN jsonb_build_object(
        'status', 'success',
        'batch_id', p_batch_id,
        'deleted_entities', v_deleted_counts
    );
END;
$function$;

-- ==============================================================================
-- Phase 5: Triggers (13 Canonical Triggers)
-- ==============================================================================

-- 1. Companies updated_at
DROP TRIGGER IF EXISTS trg_companies_updated_at ON public.companies;
CREATE TRIGGER trg_companies_updated_at
    BEFORE UPDATE ON public.companies
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 2. Profiles updated_at
DROP TRIGGER IF EXISTS trg_profiles_updated_at ON public.profiles;
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 3. Profiles column security
DROP TRIGGER IF EXISTS trg_profiles_column_security ON public.profiles;
CREATE TRIGGER trg_profiles_column_security
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION check_profile_column_security();

-- 4. Bank Accounts updated_at
DROP TRIGGER IF EXISTS trg_bank_accounts_updated_at ON public.company_bank_accounts;
CREATE TRIGGER trg_bank_accounts_updated_at
    BEFORE UPDATE ON public.company_bank_accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 5. Legal Rep updated_at
DROP TRIGGER IF EXISTS trg_legal_rep_updated_at ON public.legal_representatives;
CREATE TRIGGER trg_legal_rep_updated_at
    BEFORE UPDATE ON public.legal_representatives
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 6. Legal Rep isolation
DROP TRIGGER IF EXISTS trg_legal_rep_isolation ON public.legal_representatives;
CREATE TRIGGER trg_legal_rep_isolation
    BEFORE INSERT OR UPDATE ON public.legal_representatives
    FOR EACH ROW EXECUTE FUNCTION check_legal_rep_company_isolation();

-- 7. PDF Templates updated_at
DROP TRIGGER IF EXISTS trg_pdf_templates_updated_at ON public.pdf_templates;
CREATE TRIGGER trg_pdf_templates_updated_at
    BEFORE UPDATE ON public.pdf_templates
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 8. PDF Mappings updated_at
DROP TRIGGER IF EXISTS trg_pdf_mappings_updated_at ON public.pdf_mappings;
CREATE TRIGGER trg_pdf_mappings_updated_at
    BEFORE UPDATE ON public.pdf_mappings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 9. PDF Mappings lifecycle check
DROP TRIGGER IF EXISTS trg_check_pdf_mappings_lifecycle ON public.pdf_mappings;
CREATE TRIGGER trg_check_pdf_mappings_lifecycle
    BEFORE INSERT OR UPDATE OR DELETE ON public.pdf_mappings
    FOR EACH ROW EXECUTE FUNCTION check_pdf_mappings_lifecycle();

-- 10. PDF Template Versions immutability
DROP TRIGGER IF EXISTS trg_immutable_template_versions ON public.pdf_template_versions;
CREATE TRIGGER trg_immutable_template_versions
    BEFORE UPDATE OR DELETE ON public.pdf_template_versions
    FOR EACH ROW EXECUTE FUNCTION prevent_template_version_mutation();

-- 11. Form Fill History isolation
DROP TRIGGER IF EXISTS trg_form_fill_history_isolation ON public.form_fill_history;
CREATE TRIGGER trg_form_fill_history_isolation
    BEFORE INSERT OR UPDATE ON public.form_fill_history
    FOR EACH ROW EXECUTE FUNCTION check_form_fill_history_isolation();

-- 12. Form Fill History immutability
DROP TRIGGER IF EXISTS trg_immutable_form_fill_history ON public.form_fill_history;
CREATE TRIGGER trg_immutable_form_fill_history
    BEFORE UPDATE OR DELETE ON public.form_fill_history
    FOR EACH ROW EXECUTE FUNCTION prevent_form_fill_history_mutation();

-- 13. Auth Users synchronization trigger
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ==============================================================================
-- Phase 6: Row Level Security (RLS) & Table Policies
-- ==============================================================================

ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_bank_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.legal_representatives ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pdf_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pdf_template_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pdf_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.form_fill_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.migration_runs ENABLE ROW LEVEL SECURITY;

-- 1. Companies Policies
DROP POLICY IF EXISTS "companies_select_own" ON public.companies;
CREATE POLICY "companies_select_own" ON public.companies
    FOR SELECT TO authenticated
    USING (id = get_user_company_id());

DROP POLICY IF EXISTS "companies_update_admin" ON public.companies;
CREATE POLICY "companies_update_admin" ON public.companies
    FOR UPDATE TO authenticated
    USING (id = get_user_company_id() AND is_admin())
    WITH CHECK (id = get_user_company_id() AND is_admin());

-- 2. Profiles Policies
DROP POLICY IF EXISTS "profiles_select_own_or_admin" ON public.profiles;
CREATE POLICY "profiles_select_own_or_admin" ON public.profiles
    FOR SELECT TO authenticated
    USING (id = auth.uid() OR (company_id = get_user_company_id() AND is_admin()));

DROP POLICY IF EXISTS "profiles_update_own_or_admin" ON public.profiles;
CREATE POLICY "profiles_update_own_or_admin" ON public.profiles
    FOR UPDATE TO authenticated
    USING (id = auth.uid() OR (company_id = get_user_company_id() AND is_admin()))
    WITH CHECK (company_id = get_user_company_id());

-- 3. Company Bank Accounts Policies
DROP POLICY IF EXISTS "bank_accounts_select_company" ON public.company_bank_accounts;
CREATE POLICY "bank_accounts_select_company" ON public.company_bank_accounts
    FOR SELECT TO authenticated
    USING (company_id = get_user_company_id());

DROP POLICY IF EXISTS "bank_accounts_all_admin" ON public.company_bank_accounts;
CREATE POLICY "bank_accounts_all_admin" ON public.company_bank_accounts
    FOR ALL TO authenticated
    USING (company_id = get_user_company_id() AND is_admin())
    WITH CHECK (company_id = get_user_company_id() AND is_admin());

-- 4. Legal Representatives Policies
DROP POLICY IF EXISTS "legal_rep_select_company" ON public.legal_representatives;
CREATE POLICY "legal_rep_select_company" ON public.legal_representatives
    FOR SELECT TO authenticated
    USING (company_id = get_user_company_id());

DROP POLICY IF EXISTS "legal_rep_all_admin" ON public.legal_representatives;
CREATE POLICY "legal_rep_all_admin" ON public.legal_representatives
    FOR ALL TO authenticated
    USING (company_id = get_user_company_id() AND is_admin())
    WITH CHECK (company_id = get_user_company_id() AND is_admin());

-- 5. PDF Templates Policies
DROP POLICY IF EXISTS "pdf_templates_select_company" ON public.pdf_templates;
CREATE POLICY "pdf_templates_select_company" ON public.pdf_templates
    FOR SELECT TO authenticated
    USING (company_id = get_user_company_id());

DROP POLICY IF EXISTS "pdf_templates_all_admin" ON public.pdf_templates;
CREATE POLICY "pdf_templates_all_admin" ON public.pdf_templates
    FOR ALL TO authenticated
    USING (company_id = get_user_company_id() AND is_admin())
    WITH CHECK (company_id = get_user_company_id() AND is_admin());

-- 6. PDF Template Versions Policies
DROP POLICY IF EXISTS "pdf_template_versions_select_company" ON public.pdf_template_versions;
CREATE POLICY "pdf_template_versions_select_company" ON public.pdf_template_versions
    FOR SELECT TO authenticated
    USING (template_id IN (SELECT id FROM public.pdf_templates WHERE company_id = get_user_company_id()));

DROP POLICY IF EXISTS "pdf_template_versions_insert_admin" ON public.pdf_template_versions;
CREATE POLICY "pdf_template_versions_insert_admin" ON public.pdf_template_versions
    FOR INSERT TO authenticated
    WITH CHECK (template_id IN (SELECT id FROM public.pdf_templates WHERE company_id = get_user_company_id()) AND is_admin());

-- 7. PDF Mappings Policies
DROP POLICY IF EXISTS "pdf_mappings_select_company" ON public.pdf_mappings;
CREATE POLICY "pdf_mappings_select_company" ON public.pdf_mappings
    FOR SELECT TO authenticated
    USING (template_version_id IN (
        SELECT v.id FROM public.pdf_template_versions v
        JOIN public.pdf_templates t ON v.template_id = t.id
        WHERE t.company_id = get_user_company_id()
    ));

DROP POLICY IF EXISTS "pdf_mappings_all_admin" ON public.pdf_mappings;
CREATE POLICY "pdf_mappings_all_admin" ON public.pdf_mappings
    FOR ALL TO authenticated
    USING (
        template_version_id IN (
            SELECT v.id FROM public.pdf_template_versions v
            JOIN public.pdf_templates t ON v.template_id = t.id
            WHERE t.company_id = get_user_company_id()
        ) AND is_admin()
    )
    WITH CHECK (
        template_version_id IN (
            SELECT v.id FROM public.pdf_template_versions v
            JOIN public.pdf_templates t ON v.template_id = t.id
            WHERE t.company_id = get_user_company_id()
        ) AND is_admin()
    );

-- 8. Form Fill History Policies
DROP POLICY IF EXISTS "history_select_own_or_admin" ON public.form_fill_history;
CREATE POLICY "history_select_own_or_admin" ON public.form_fill_history
    FOR SELECT TO authenticated
    USING (company_id = get_user_company_id() AND (operator_user_id = auth.uid() OR is_admin()));

DROP POLICY IF EXISTS "history_insert_operator" ON public.form_fill_history;
CREATE POLICY "history_insert_operator" ON public.form_fill_history
    FOR INSERT TO authenticated
    WITH CHECK (company_id = get_user_company_id() AND operator_user_id = auth.uid());

-- 9. Migration Runs Policies
DROP POLICY IF EXISTS "migration_runs_select_admin" ON public.migration_runs;
CREATE POLICY "migration_runs_select_admin" ON public.migration_runs
    FOR SELECT TO authenticated
    USING (is_admin());

-- ==============================================================================
-- Phase 7: Storage Buckets & Policies (Idempotent)
-- ==============================================================================

INSERT INTO storage.buckets (id, name, public)
VALUES 
    ('templates', 'templates', false),
    ('signatures', 'signatures', false),
    ('generated-pdfs', 'generated-pdfs', false)
ON CONFLICT (id) DO NOTHING;

DROP POLICY IF EXISTS "storage_templates_select" ON storage.objects;
CREATE POLICY "storage_templates_select" ON storage.objects
    FOR SELECT TO authenticated
    USING (bucket_id = 'templates' AND ((storage.foldername(name))[1])::uuid = get_user_company_id());

DROP POLICY IF EXISTS "storage_templates_all_admin" ON storage.objects;
CREATE POLICY "storage_templates_all_admin" ON storage.objects
    FOR ALL TO authenticated
    USING (bucket_id = 'templates' AND ((storage.foldername(name))[1])::uuid = get_user_company_id() AND is_admin())
    WITH CHECK (bucket_id = 'templates' AND ((storage.foldername(name))[1])::uuid = get_user_company_id() AND is_admin());

DROP POLICY IF EXISTS "storage_signatures_select" ON storage.objects;
CREATE POLICY "storage_signatures_select" ON storage.objects
    FOR SELECT TO authenticated
    USING (bucket_id = 'signatures' AND ((storage.foldername(name))[1])::uuid = get_user_company_id());

DROP POLICY IF EXISTS "storage_signatures_all_admin" ON storage.objects;
CREATE POLICY "storage_signatures_all_admin" ON storage.objects
    FOR ALL TO authenticated
    USING (bucket_id = 'signatures' AND ((storage.foldername(name))[1])::uuid = get_user_company_id() AND is_admin())
    WITH CHECK (bucket_id = 'signatures' AND ((storage.foldername(name))[1])::uuid = get_user_company_id() AND is_admin());

DROP POLICY IF EXISTS "storage_generated_pdfs_select" ON storage.objects;
CREATE POLICY "storage_generated_pdfs_select" ON storage.objects
    FOR SELECT TO authenticated
    USING (bucket_id = 'generated-pdfs' AND ((storage.foldername(name))[1])::uuid = get_user_company_id() AND (((storage.foldername(name))[2])::uuid = auth.uid() OR is_admin()));

DROP POLICY IF EXISTS "storage_generated_pdfs_insert" ON storage.objects;
CREATE POLICY "storage_generated_pdfs_insert" ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (bucket_id = 'generated-pdfs' AND ((storage.foldername(name))[1])::uuid = get_user_company_id() AND ((storage.foldername(name))[2])::uuid = auth.uid());
