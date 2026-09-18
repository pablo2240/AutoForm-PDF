-- ============================================================================
-- AutoForm PDF: Selective Rollback & Attribute Security Hardening
-- Migration: 20260918000004_selective_rollback_and_attribute_security.sql
--
-- 1. Batch ID tracking for selective migration rollback:
--    Adds migration_batch_id UUID to all application tables.
-- 2. Manifest and Run Tracking:
--    Creates public.migration_runs table.
-- 3. Stored Procedure for Selective Rollback:
--    public.rollback_migration_batch(p_batch_id UUID)
-- 4. Attribute Security Hardening:
--    - handle_new_user(): cargo and documento_identidad are NEVER synced from
--      raw_user_meta_data on UPDATE. Only raw_app_meta_data (admin) can change them.
--    - check_profile_column_security(): commercial users are blocked from updating
--      cargo, tipo_documento, and documento_identidad directly on public.profiles.
-- 5. Safe Synthetic Teardown for Controlled E2E Tests:
--    Allows DELETE on form_fill_history strictly for synthetic test companies
--    (00000000-0000-0000-0000-*), maintaining 100% immutability for real entities.
-- ============================================================================

-- 1. Add migration_batch_id to all application tables
ALTER TABLE public.companies 
    ADD COLUMN IF NOT EXISTS migration_batch_id UUID;

ALTER TABLE public.profiles 
    ADD COLUMN IF NOT EXISTS migration_batch_id UUID;

ALTER TABLE public.company_bank_accounts 
    ADD COLUMN IF NOT EXISTS migration_batch_id UUID;

ALTER TABLE public.legal_representatives 
    ADD COLUMN IF NOT EXISTS migration_batch_id UUID;

ALTER TABLE public.pdf_templates 
    ADD COLUMN IF NOT EXISTS migration_batch_id UUID;

ALTER TABLE public.pdf_template_versions 
    ADD COLUMN IF NOT EXISTS migration_batch_id UUID;

ALTER TABLE public.pdf_mappings 
    ADD COLUMN IF NOT EXISTS migration_batch_id UUID;

-- Indexes for efficient batch queries and deletions
CREATE INDEX IF NOT EXISTS idx_companies_batch ON public.companies(migration_batch_id);
CREATE INDEX IF NOT EXISTS idx_profiles_batch ON public.profiles(migration_batch_id);
CREATE INDEX IF NOT EXISTS idx_bank_accounts_batch ON public.company_bank_accounts(migration_batch_id);
CREATE INDEX IF NOT EXISTS idx_legal_rep_batch ON public.legal_representatives(migration_batch_id);
CREATE INDEX IF NOT EXISTS idx_pdf_templates_batch ON public.pdf_templates(migration_batch_id);
CREATE INDEX IF NOT EXISTS idx_pdf_versions_batch ON public.pdf_template_versions(migration_batch_id);
CREATE INDEX IF NOT EXISTS idx_pdf_mappings_batch ON public.pdf_mappings(migration_batch_id);

-- 2. Create public.migration_runs table
CREATE TABLE IF NOT EXISTS public.migration_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL UNIQUE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'rolled_back', 'failed')),
    target_project_ref VARCHAR(50) NOT NULL,
    manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_migration_runs_batch ON public.migration_runs(batch_id);

ALTER TABLE public.migration_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "migration_runs_select_admin" ON public.migration_runs;
CREATE POLICY "migration_runs_select_admin" ON public.migration_runs
    FOR SELECT TO authenticated
    USING (public.is_admin());

-- 3. Stored Procedure for Selective Rollback by migration_batch_id
CREATE OR REPLACE FUNCTION public.rollback_migration_batch(p_batch_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

-- 4. Hardened check_profile_column_security()
-- Disallow non-admin modification of: company_id, role, is_active, email, cargo, tipo_documento, documento_identidad
CREATE OR REPLACE FUNCTION public.check_profile_column_security()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
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
$$;

-- 5. Hardened handle_new_user()
-- cargo and documento_identidad are strictly administrative. On UPDATE, they NEVER sync from raw_user_meta_data.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT OR UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 6. Safe Synthetic Teardown in prevent_form_fill_history_mutation()
-- Allows DELETE strictly for synthetic test company records (00000000-0000-0000-0000-*),
-- keeping real production audit records 100% immutable.
CREATE OR REPLACE FUNCTION public.prevent_form_fill_history_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

-- 7. Safe Synthetic Teardown & Selective Rollback in prevent_template_version_mutation()
-- Allows DELETE during rollback of migration batch OR for synthetic test entities (00000000-0000-0000-0000-*)
CREATE OR REPLACE FUNCTION public.prevent_template_version_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;
