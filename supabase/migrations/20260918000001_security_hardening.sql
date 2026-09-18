-- ==============================================================================
-- AutoForm PDF: Security Hardening & Isolation Refinements
-- Migration: 20260918000001_security_hardening.sql
-- ==============================================================================

-- 1. Support legal_rep_only: Make commercial_profile_id nullable in form_fill_history
ALTER TABLE public.form_fill_history 
    ALTER COLUMN commercial_profile_id DROP NOT NULL;

-- 2. Update Cross-Company Trigger on form_fill_history to handle null commercial_profile_id
CREATE OR REPLACE FUNCTION public.check_form_fill_history_isolation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    -- 1. Operator must belong to the specified company
    IF NOT EXISTS (
        SELECT 1 FROM public.profiles 
        WHERE id = NEW.operator_user_id AND company_id = NEW.company_id
    ) THEN
        RAISE EXCEPTION 'Cross-company violation: operator_user_id % does not belong to company %', NEW.operator_user_id, NEW.company_id;
    END IF;

    -- 2. If commercial profile is specified, it must belong to the same company
    IF NEW.commercial_profile_id IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1 FROM public.profiles 
            WHERE id = NEW.commercial_profile_id AND company_id = NEW.company_id
        ) THEN
            RAISE EXCEPTION 'Cross-company violation: commercial_profile_id % does not belong to company %', NEW.commercial_profile_id, NEW.company_id;
        END IF;
    END IF;

    -- 3. Template version must belong to a template of the specified company
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
$$;

-- 3. Security Hardening for handle_new_user:
-- company_id and role MUST come from raw_app_meta_data (server-set via admin API).
-- Client-set raw_user_meta_data is completely ignored for company_id and role.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
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
BEGIN
    -- Strict security: company_id MUST be set in raw_app_meta_data by admin
    IF NEW.raw_app_meta_data->>'company_id' IS NULL THEN
        RAISE EXCEPTION 'Cannot register user: company_id is required in app_metadata (server-side only)';
    END IF;

    BEGIN
        v_company_id := (NEW.raw_app_meta_data->>'company_id')::UUID;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Cannot register user: invalid UUID for company_id in app_metadata';
    END;

    -- Verify target company existence and active state
    IF NOT EXISTS (SELECT 1 FROM public.companies WHERE id = v_company_id AND is_active = true) THEN
        RAISE EXCEPTION 'Cannot register user: target company does not exist or is inactive';
    END IF;

    -- Strict check: domain whitelist
    IF NOT (LOWER(NEW.email) ~* '^[^@\s]+@(iaclatam\.com|iac\.com\.co)$') THEN
        RAISE EXCEPTION 'Cannot register user: email domain % is not authorized', NEW.email;
    END IF;

    -- Role MUST come from raw_app_meta_data (defaults to 'commercial' if omitted, rejects arbitrary roles)
    v_role := LOWER(COALESCE(NEW.raw_app_meta_data->>'role', 'commercial'));
    IF v_role NOT IN ('admin', 'commercial') THEN
        RAISE EXCEPTION 'Cannot register user: invalid role % in app_metadata', v_role;
    END IF;

    -- Non-privileged attributes come from user_metadata (or fallbacks)
    v_nombre := TRIM(COALESCE(NEW.raw_user_meta_data->>'nombre', ''));
    v_apellido := TRIM(COALESCE(NEW.raw_user_meta_data->>'apellido', ''));
    v_cargo := TRIM(COALESCE(NEW.raw_user_meta_data->>'cargo', ''));
    v_celular := TRIM(COALESCE(NEW.raw_user_meta_data->>'celular', ''));
    v_tipo_doc := COALESCE(NEW.raw_user_meta_data->>'tipo_documento', 'C.C');
    v_doc_id := NEW.raw_user_meta_data->>'documento_identidad';

    -- Strict validation: No dummy or empty strings
    IF char_length(v_nombre) < 2 OR char_length(v_apellido) < 2 OR char_length(v_cargo) < 2 OR char_length(v_celular) < 5 THEN
        RAISE EXCEPTION 'Cannot register user: missing or invalid profile attributes (nombre, apellido, cargo, celular)';
    END IF;

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
        is_active
    ) VALUES (
        NEW.id,
        v_company_id,
        LOWER(NEW.email),
        v_nombre,
        v_apellido,
        v_nombre || ' ' || v_apellido,
        v_cargo,
        v_celular,
        v_tipo_doc,
        v_doc_id,
        v_role,
        true
    );

    RETURN NEW;
END;
$$;

-- 4. Inmutable Versioning for pdf_template_versions
-- Drop all-access policy on pdf_template_versions
DROP POLICY IF EXISTS "pdf_template_versions_all_admin" ON public.pdf_template_versions;

-- Admins can only INSERT versions (never UPDATE or DELETE!)
CREATE POLICY "pdf_template_versions_insert_admin" ON public.pdf_template_versions
    FOR INSERT TO authenticated
    WITH CHECK (
        template_id IN (
            SELECT id FROM public.pdf_templates WHERE company_id = public.get_user_company_id()
        ) AND public.is_admin()
    );

-- Trigger to physically prevent UPDATE and DELETE on template versions
CREATE OR REPLACE FUNCTION public.prevent_template_version_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Template versions are immutable: UPDATE and DELETE are prohibited. Create a new version instead.';
END;
$$;

DROP TRIGGER IF EXISTS trg_immutable_template_versions ON public.pdf_template_versions;
CREATE TRIGGER trg_immutable_template_versions
    BEFORE UPDATE OR DELETE ON public.pdf_template_versions
    FOR EACH ROW EXECUTE FUNCTION public.prevent_template_version_mutation();

-- 5. Immutability for pdf_mappings with historical runs
CREATE OR REPLACE FUNCTION public.prevent_historical_mappings_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
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
$$;

DROP TRIGGER IF EXISTS trg_immutable_mappings_with_history ON public.pdf_mappings;
CREATE TRIGGER trg_immutable_mappings_with_history
    BEFORE UPDATE OR DELETE ON public.pdf_mappings
    FOR EACH ROW EXECUTE FUNCTION public.prevent_historical_mappings_mutation();

-- 6. Storage Policies Hardening: {company_id}/{operator_user_id}/{history_id}.pdf
DROP POLICY IF EXISTS "storage_generated_pdfs_select" ON storage.objects;
DROP POLICY IF EXISTS "storage_generated_pdfs_insert_auth" ON storage.objects;

-- Select: Operator reads own files; Admin reads all files in company
CREATE POLICY "storage_generated_pdfs_select" ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id = 'generated-pdfs' AND 
        (storage.foldername(name))[1]::uuid = public.get_user_company_id() AND
        (
            (storage.foldername(name))[2]::uuid = auth.uid() OR
            public.is_admin()
        )
    );

-- Insert: Operator can only write to their own folder: {company_id}/{auth.uid()}/...
CREATE POLICY "storage_generated_pdfs_insert" ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id = 'generated-pdfs' AND 
        (storage.foldername(name))[1]::uuid = public.get_user_company_id() AND
        (storage.foldername(name))[2]::uuid = auth.uid()
    );

-- NO UPDATE or DELETE policies on storage.objects for generated-pdfs!

-- 7. Strict Table Grants (Least Privilege / Defense-in-Depth)
-- Revoke all from anon and public
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, public;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, public;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, public;

-- Grant specific operations to authenticated
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM authenticated;

-- companies: SELECT for members, UPDATE for admin (handled by RLS)
GRANT SELECT, UPDATE ON public.companies TO authenticated;

-- profiles: SELECT, UPDATE, DELETE (handled by RLS & column security trigger; NO INSERT via SQL)
GRANT SELECT, UPDATE, DELETE ON public.profiles TO authenticated;

-- company_bank_accounts: CRUD for admins (RLS restricted)
GRANT SELECT, INSERT, UPDATE, DELETE ON public.company_bank_accounts TO authenticated;

-- legal_representatives: CRUD for admins (RLS restricted)
GRANT SELECT, INSERT, UPDATE, DELETE ON public.legal_representatives TO authenticated;

-- pdf_templates: CRUD for admins (RLS restricted)
GRANT SELECT, INSERT, UPDATE, DELETE ON public.pdf_templates TO authenticated;

-- pdf_template_versions: SELECT and INSERT only (strictly NO UPDATE, NO DELETE)
GRANT SELECT, INSERT ON public.pdf_template_versions TO authenticated;

-- pdf_mappings: CRUD for admins (RLS and historical trigger restricted)
GRANT SELECT, INSERT, UPDATE, DELETE ON public.pdf_mappings TO authenticated;

-- form_fill_history: SELECT and INSERT only (strictly NO UPDATE, NO DELETE)
GRANT SELECT, INSERT ON public.form_fill_history TO authenticated;

-- RPC functions
GRANT EXECUTE ON FUNCTION public.get_user_company_id() TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_admin() TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_company_commercial_profiles() TO authenticated;
