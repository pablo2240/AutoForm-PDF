-- ==============================================================================
-- AutoForm PDF: Lifecycle Management & Defense-in-Depth Hardening
-- Migration: 20260918000002_lifecycle_and_hardening.sql
-- ==============================================================================

-- 1. Add Lifecycle Status to pdf_template_versions
ALTER TABLE public.pdf_template_versions 
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft' 
    CHECK (status IN ('draft', 'published', 'retired'));

-- 2. Update Mutation Trigger on pdf_template_versions:
-- Prohibits DELETE completely.
-- Permits UPDATE ONLY for valid status transitions (draft -> published -> retired).
-- Prohibits modifying any other column (version, storage_path, filename, etc.).
CREATE OR REPLACE FUNCTION public.prevent_template_version_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Template versions are immutable: DELETE is prohibited.';
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
        ELSIF OLD.status = 'published' AND NEW.status = 'retired' THEN
            RETURN NEW;
        ELSIF OLD.status = NEW.status THEN
            RETURN NEW;
        ELSE
            RAISE EXCEPTION 'Invalid template version status transition from % to %', OLD.status, NEW.status;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_immutable_template_versions ON public.pdf_template_versions;
CREATE TRIGGER trg_immutable_template_versions
    BEFORE UPDATE OR DELETE ON public.pdf_template_versions
    FOR EACH ROW EXECUTE FUNCTION public.prevent_template_version_mutation();

-- 3. Template Version Lifecycle RPCs (Admin only)
CREATE OR REPLACE FUNCTION public.publish_template_version(p_version_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

CREATE OR REPLACE FUNCTION public.retire_template_version(p_version_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

-- 4. PDF Mappings Lifecycle Trigger:
-- Mappings can ONLY be inserted, updated, or deleted if the target version is in 'draft' status.
CREATE OR REPLACE FUNCTION public.check_pdf_mappings_lifecycle()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

DROP TRIGGER IF EXISTS trg_immutable_mappings_with_history ON public.pdf_mappings;
DROP TRIGGER IF EXISTS trg_check_pdf_mappings_lifecycle ON public.pdf_mappings;
CREATE TRIGGER trg_check_pdf_mappings_lifecycle
    BEFORE INSERT OR UPDATE OR DELETE ON public.pdf_mappings
    FOR EACH ROW EXECUTE FUNCTION public.check_pdf_mappings_lifecycle();

-- 5. Form Fill Lifecycle RPCs & Terminal State Immutability
CREATE OR REPLACE FUNCTION public.start_form_fill(
    p_template_version_id UUID,
    p_commercial_profile_id UUID DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

CREATE OR REPLACE FUNCTION public.complete_form_fill(
    p_history_id UUID,
    p_output_storage_path TEXT,
    p_metadata JSONB DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

CREATE OR REPLACE FUNCTION public.fail_form_fill(
    p_history_id UUID,
    p_error_message TEXT,
    p_metadata JSONB DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

CREATE OR REPLACE FUNCTION public.prevent_form_fill_history_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'form_fill_history records are audit logs and cannot be deleted';
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

DROP TRIGGER IF EXISTS trg_immutable_form_fill_history ON public.form_fill_history;
CREATE TRIGGER trg_immutable_form_fill_history
    BEFORE UPDATE OR DELETE ON public.form_fill_history
    FOR EACH ROW EXECUTE FUNCTION public.prevent_form_fill_history_mutation();

-- 6. Revoke DELETE on public.profiles & Drop profiles_delete_admin
DROP POLICY IF EXISTS "profiles_delete_admin" ON public.profiles;
REVOKE DELETE ON public.profiles FROM authenticated, anon, public;

-- 7. Hardening All SECURITY DEFINER Functions with empty search_path = ''
CREATE OR REPLACE FUNCTION public.get_user_company_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT company_id 
    FROM public.profiles 
    WHERE id = auth.uid() 
      AND is_active = true;
$$;

CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT EXISTS (
        SELECT 1 
        FROM public.profiles 
        WHERE id = auth.uid() 
          AND role = 'admin' 
          AND is_active = true
    );
$$;

CREATE OR REPLACE FUNCTION public.get_company_commercial_profiles()
RETURNS TABLE (
    id UUID,
    company_id UUID,
    display_name VARCHAR(150),
    cargo VARCHAR(100),
    email VARCHAR(255),
    celular VARCHAR(50),
    is_active BOOLEAN
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

CREATE OR REPLACE FUNCTION public.check_form_fill_history_isolation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

CREATE OR REPLACE FUNCTION public.check_profile_column_security()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
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
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.check_legal_rep_company_isolation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
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
$$;

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
BEGIN
    IF NEW.raw_app_meta_data->>'company_id' IS NULL THEN
        RAISE EXCEPTION 'Cannot register user: company_id is required in app_metadata (server-side only)';
    END IF;

    BEGIN
        v_company_id := (NEW.raw_app_meta_data->>'company_id')::UUID;
    EXCEPTION WHEN OTHERS THEN
        RAISE EXCEPTION 'Cannot register user: invalid UUID for company_id in app_metadata';
    END;

    IF NOT EXISTS (SELECT 1 FROM public.companies WHERE id = v_company_id AND is_active = true) THEN
        RAISE EXCEPTION 'Cannot register user: target company does not exist or is inactive';
    END IF;

    IF NOT (LOWER(NEW.email) ~* '^[^@\s]+@(iaclatam\.com|iac\.com\.co)$') THEN
        RAISE EXCEPTION 'Cannot register user: email domain % is not authorized', NEW.email;
    END IF;

    v_role := LOWER(COALESCE(NEW.raw_app_meta_data->>'role', 'commercial'));
    IF v_role NOT IN ('admin', 'commercial') THEN
        RAISE EXCEPTION 'Cannot register user: invalid role % in app_metadata', v_role;
    END IF;

    v_nombre := TRIM(COALESCE(NEW.raw_user_meta_data->>'nombre', ''));
    v_apellido := TRIM(COALESCE(NEW.raw_user_meta_data->>'apellido', ''));
    v_cargo := TRIM(COALESCE(NEW.raw_user_meta_data->>'cargo', ''));
    v_celular := TRIM(COALESCE(NEW.raw_user_meta_data->>'celular', ''));
    v_tipo_doc := COALESCE(NEW.raw_user_meta_data->>'tipo_documento', 'C.C');
    v_doc_id := NEW.raw_user_meta_data->>'documento_identidad';

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

-- 8. Explicit Execution Permissions (Defense-in-depth)
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, public;

GRANT EXECUTE ON FUNCTION public.get_user_company_id() TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_admin() TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_company_commercial_profiles() TO authenticated;
GRANT EXECUTE ON FUNCTION public.publish_template_version(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.retire_template_version(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.start_form_fill(UUID, UUID, JSONB) TO authenticated;
GRANT EXECUTE ON FUNCTION public.complete_form_fill(UUID, TEXT, JSONB) TO authenticated;
GRANT EXECUTE ON FUNCTION public.fail_form_fill(UUID, TEXT, JSONB) TO authenticated;
