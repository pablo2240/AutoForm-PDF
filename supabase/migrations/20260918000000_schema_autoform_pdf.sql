-- ==============================================================================
-- AutoForm PDF (SmartFormAI) - Complete Supabase PostgreSQL Schema
-- Migration: 20260918000000_schema_autoform_pdf.sql
-- Pure DDL: Zero PII, Zero Seed Data, Strict Multi-Tenant Isolation
-- ==============================================================================

-- 1. Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 2. Tables & Primary Constraints
-- ==============================================================================

-- 2.1 Companies (Root Tenant Entity)
CREATE TABLE public.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    razon_social VARCHAR(255) NOT NULL,
    nombre_comercial VARCHAR(100),
    nit VARCHAR(20) NOT NULL UNIQUE,
    dv VARCHAR(2) NOT NULL CHECK (dv ~ '^[0-9]{1,2}$'),
    pais VARCHAR(100) NOT NULL DEFAULT 'Colombia',
    departamento VARCHAR(100),
    ciudad VARCHAR(100),
    direccion_principal TEXT,
    telefono VARCHAR(50),
    pagina_web VARCHAR(255),
    total_activos NUMERIC(20, 2),
    total_pasivos NUMERIC(20, 2),
    total_patrimonio NUMERIC(20, 2),
    total_ingresos_mensuales NUMERIC(20, 2),
    total_egresos_mensuales NUMERIC(20, 2),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2.2 Profiles (Linked to auth.users)
CREATE TABLE public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    email VARCHAR(255) NOT NULL,
    nombre VARCHAR(100) NOT NULL CHECK (char_length(TRIM(nombre)) >= 2),
    apellido VARCHAR(100) NOT NULL CHECK (char_length(TRIM(apellido)) >= 2),
    display_name VARCHAR(150) NOT NULL,
    cargo VARCHAR(100) NOT NULL CHECK (char_length(TRIM(cargo)) >= 2),
    celular VARCHAR(50) NOT NULL,
    tipo_documento VARCHAR(20) NOT NULL DEFAULT 'C.C',
    documento_identidad VARCHAR(50), -- Sensitive PII
    role VARCHAR(30) NOT NULL DEFAULT 'commercial' CHECK (role IN ('admin', 'commercial')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_profiles_corporate_email CHECK (LOWER(email) ~* '^[^@\s]+@(iaclatam\.com|iac\.com\.co)$')
);

CREATE UNIQUE INDEX uq_profiles_email_lower ON public.profiles(LOWER(email));
CREATE INDEX idx_profiles_company ON public.profiles(company_id);

-- 2.3 Company Bank Accounts
CREATE TABLE public.company_bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    entidad_bancaria VARCHAR(100) NOT NULL,
    tipo_cuenta VARCHAR(50) NOT NULL CHECK (tipo_cuenta IN ('Ahorros', 'Corriente')),
    numero_cuenta VARCHAR(50) NOT NULL,
    es_principal BOOLEAN NOT NULL DEFAULT false,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_principal_bank_account ON public.company_bank_accounts(company_id) 
WHERE es_principal = true AND activo = true;

CREATE INDEX idx_bank_accounts_company ON public.company_bank_accounts(company_id);

-- 2.4 Legal Representatives
CREATE TABLE public.legal_representatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    user_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    nombre_completo VARCHAR(200) NOT NULL,
    nombres VARCHAR(100) NOT NULL,
    apellidos VARCHAR(100) NOT NULL,
    tipo_documento VARCHAR(20) NOT NULL DEFAULT 'C.C',
    numero_documento VARCHAR(50) NOT NULL,
    lugar_expedicion VARCHAR(100),
    fecha_expedicion DATE,
    email VARCHAR(255),
    celular VARCHAR(50),
    firma_storage_path VARCHAR(255),
    es_principal BOOLEAN NOT NULL DEFAULT true,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_legal_rep_company ON public.legal_representatives(company_id);

-- 2.5 PDF Templates (Logical Template Entity)
CREATE TABLE public.pdf_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    codigo VARCHAR(100) NOT NULL,
    nombre VARCHAR(255) NOT NULL,
    descripcion TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_pdf_templates_company_codigo UNIQUE (company_id, codigo)
);

CREATE INDEX idx_pdf_templates_company ON public.pdf_templates(company_id);

-- 2.6 PDF Template Versions (Physical / Versioned Template Entity)
CREATE TABLE public.pdf_template_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES public.pdf_templates(id) ON DELETE CASCADE,
    version INT NOT NULL CHECK (version >= 1),
    filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    page_count INT NOT NULL CHECK (page_count >= 1),
    is_acroform BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_template_version UNIQUE (template_id, version)
);

CREATE INDEX idx_template_versions_template ON public.pdf_template_versions(template_id);

-- 2.7 PDF Mappings (Semantic & Geometric Bindings for a Version)
CREATE TABLE public.pdf_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_version_id UUID NOT NULL REFERENCES public.pdf_template_versions(id) ON DELETE CASCADE,
    field_key VARCHAR(150) NOT NULL,
    category VARCHAR(100) NOT NULL,
    source_path VARCHAR(255) NOT NULL,
    page_index INT NOT NULL CHECK (page_index >= 0),
    coordinates JSONB,
    field_type VARCHAR(50) NOT NULL DEFAULT 'text',
    validation_rules JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_pdf_mappings_version ON public.pdf_mappings(template_version_id);

-- 2.8 Form Fill History (Audit & Run History)
CREATE TABLE public.form_fill_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    template_version_id UUID NOT NULL REFERENCES public.pdf_template_versions(id) ON DELETE RESTRICT,
    operator_user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    commercial_profile_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    status VARCHAR(50) NOT NULL CHECK (status IN ('draft', 'processing', 'completed', 'failed')),
    output_storage_path VARCHAR(500),
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_completed_has_output CHECK (status != 'completed' OR output_storage_path IS NOT NULL)
);

CREATE INDEX idx_history_company ON public.form_fill_history(company_id);
CREATE INDEX idx_history_operator ON public.form_fill_history(operator_user_id);
CREATE INDEX idx_history_version ON public.form_fill_history(template_version_id);

-- ==============================================================================
-- 3. Security Helper Functions (SECURITY DEFINER, Safe search_path)
-- ==============================================================================

-- 3.1 Get Company ID of currently authenticated active user
CREATE OR REPLACE FUNCTION public.get_user_company_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT company_id 
    FROM public.profiles 
    WHERE id = auth.uid() 
      AND is_active = true;
$$;

-- 3.2 Check if currently authenticated active user is admin
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 
        FROM public.profiles 
        WHERE id = auth.uid() 
          AND role = 'admin' 
          AND is_active = true
    );
$$;

-- 3.3 RPC: Secure Commercial Profiles Provider (No sensitive PII exposed)
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
SET search_path = public, pg_temp
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

-- ==============================================================================
-- 4. Triggers & Data Integrity Functions
-- ==============================================================================

-- 4.1 Update Timestamp Trigger Function
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_companies_updated_at BEFORE UPDATE ON public.companies FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_profiles_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_bank_accounts_updated_at BEFORE UPDATE ON public.company_bank_accounts FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_legal_rep_updated_at BEFORE UPDATE ON public.legal_representatives FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_pdf_templates_updated_at BEFORE UPDATE ON public.pdf_templates FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_pdf_mappings_updated_at BEFORE UPDATE ON public.pdf_mappings FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- 4.2 Safe Auth User Insertion Trigger (Admin Invitation Model)
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
    -- Strict check: company_id is REQUIRED in metadata. No fallback.
    IF NEW.raw_user_meta_data->>'company_id' IS NULL THEN
        RAISE EXCEPTION 'Cannot register user: company_id is required in user metadata';
    END IF;

    v_company_id := (NEW.raw_user_meta_data->>'company_id')::UUID;

    -- Verify company existence and active state
    IF NOT EXISTS (SELECT 1 FROM public.companies WHERE id = v_company_id AND is_active = true) THEN
        RAISE EXCEPTION 'Cannot register user: target company does not exist or is inactive';
    END IF;

    -- Strict check: domain whitelist
    IF NOT (LOWER(NEW.email) ~* '^[^@\s]+@(iaclatam\.com|iac\.com\.co)$') THEN
        RAISE EXCEPTION 'Cannot register user: email domain % is not authorized', NEW.email;
    END IF;

    v_nombre := TRIM(COALESCE(NEW.raw_user_meta_data->>'nombre', ''));
    v_apellido := TRIM(COALESCE(NEW.raw_user_meta_data->>'apellido', ''));
    v_cargo := TRIM(COALESCE(NEW.raw_user_meta_data->>'cargo', ''));
    v_celular := TRIM(COALESCE(NEW.raw_user_meta_data->>'celular', ''));
    v_role := LOWER(COALESCE(NEW.raw_user_meta_data->>'role', 'commercial'));
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

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 4.3 Profile Column Security Trigger (Restricts Standard Commercial Modifications)
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
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_profiles_column_security
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.check_profile_column_security();

-- 4.4 Legal Representative Cross-Company Isolation Trigger
CREATE OR REPLACE FUNCTION public.check_legal_rep_company_isolation()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
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

CREATE TRIGGER trg_legal_rep_isolation
    BEFORE INSERT OR UPDATE ON public.legal_representatives
    FOR EACH ROW EXECUTE FUNCTION public.check_legal_rep_company_isolation();

-- 4.5 Form Fill History Cross-Company Isolation Trigger
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

    -- 2. Commercial profile must belong to the specified company
    IF NOT EXISTS (
        SELECT 1 FROM public.profiles 
        WHERE id = NEW.commercial_profile_id AND company_id = NEW.company_id
    ) THEN
        RAISE EXCEPTION 'Cross-company violation: commercial_profile_id % does not belong to company %', NEW.commercial_profile_id, NEW.company_id;
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

CREATE TRIGGER trg_form_fill_history_isolation
    BEFORE INSERT OR UPDATE ON public.form_fill_history
    FOR EACH ROW EXECUTE FUNCTION public.check_form_fill_history_isolation();

-- ==============================================================================
-- 5. Row Level Security (RLS) Policies
-- ==============================================================================

ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_bank_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.legal_representatives ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pdf_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pdf_template_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pdf_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.form_fill_history ENABLE ROW LEVEL SECURITY;

-- 5.1 Companies RLS
CREATE POLICY "companies_select_own" ON public.companies
    FOR SELECT TO authenticated
    USING (id = public.get_user_company_id());

CREATE POLICY "companies_update_admin" ON public.companies
    FOR UPDATE TO authenticated
    USING (id = public.get_user_company_id() AND public.is_admin())
    WITH CHECK (id = public.get_user_company_id() AND public.is_admin());

-- 5.2 Profiles RLS
CREATE POLICY "profiles_select_own_or_admin" ON public.profiles
    FOR SELECT TO authenticated
    USING (id = auth.uid() OR (company_id = public.get_user_company_id() AND public.is_admin()));

CREATE POLICY "profiles_update_own_or_admin" ON public.profiles
    FOR UPDATE TO authenticated
    USING (id = auth.uid() OR (company_id = public.get_user_company_id() AND public.is_admin()))
    WITH CHECK (company_id = public.get_user_company_id());

CREATE POLICY "profiles_delete_admin" ON public.profiles
    FOR DELETE TO authenticated
    USING (company_id = public.get_user_company_id() AND public.is_admin());

-- 5.3 Company Bank Accounts RLS
CREATE POLICY "bank_accounts_select_company" ON public.company_bank_accounts
    FOR SELECT TO authenticated
    USING (company_id = public.get_user_company_id());

CREATE POLICY "bank_accounts_all_admin" ON public.company_bank_accounts
    FOR ALL TO authenticated
    USING (company_id = public.get_user_company_id() AND public.is_admin())
    WITH CHECK (company_id = public.get_user_company_id() AND public.is_admin());

-- 5.4 Legal Representatives RLS
CREATE POLICY "legal_rep_select_company" ON public.legal_representatives
    FOR SELECT TO authenticated
    USING (company_id = public.get_user_company_id());

CREATE POLICY "legal_rep_all_admin" ON public.legal_representatives
    FOR ALL TO authenticated
    USING (company_id = public.get_user_company_id() AND public.is_admin())
    WITH CHECK (company_id = public.get_user_company_id() AND public.is_admin());

-- 5.5 PDF Templates RLS
CREATE POLICY "pdf_templates_select_company" ON public.pdf_templates
    FOR SELECT TO authenticated
    USING (company_id = public.get_user_company_id());

CREATE POLICY "pdf_templates_all_admin" ON public.pdf_templates
    FOR ALL TO authenticated
    USING (company_id = public.get_user_company_id() AND public.is_admin())
    WITH CHECK (company_id = public.get_user_company_id() AND public.is_admin());

-- 5.6 PDF Template Versions RLS
CREATE POLICY "pdf_template_versions_select_company" ON public.pdf_template_versions
    FOR SELECT TO authenticated
    USING (template_id IN (
        SELECT id FROM public.pdf_templates WHERE company_id = public.get_user_company_id()
    ));

CREATE POLICY "pdf_template_versions_all_admin" ON public.pdf_template_versions
    FOR ALL TO authenticated
    USING (template_id IN (
        SELECT id FROM public.pdf_templates WHERE company_id = public.get_user_company_id()
    ) AND public.is_admin())
    WITH CHECK (template_id IN (
        SELECT id FROM public.pdf_templates WHERE company_id = public.get_user_company_id()
    ) AND public.is_admin());

-- 5.7 PDF Mappings RLS
CREATE POLICY "pdf_mappings_select_company" ON public.pdf_mappings
    FOR SELECT TO authenticated
    USING (template_version_id IN (
        SELECT v.id FROM public.pdf_template_versions v
        JOIN public.pdf_templates t ON v.template_id = t.id
        WHERE t.company_id = public.get_user_company_id()
    ));

CREATE POLICY "pdf_mappings_all_admin" ON public.pdf_mappings
    FOR ALL TO authenticated
    USING (template_version_id IN (
        SELECT v.id FROM public.pdf_template_versions v
        JOIN public.pdf_templates t ON v.template_id = t.id
        WHERE t.company_id = public.get_user_company_id()
    ) AND public.is_admin())
    WITH CHECK (template_version_id IN (
        SELECT v.id FROM public.pdf_template_versions v
        JOIN public.pdf_templates t ON v.template_id = t.id
        WHERE t.company_id = public.get_user_company_id()
    ) AND public.is_admin());

-- 5.8 Form Fill History RLS (Append-Only Audit Trail)
CREATE POLICY "history_select_own_or_admin" ON public.form_fill_history
    FOR SELECT TO authenticated
    USING (company_id = public.get_user_company_id() AND (operator_user_id = auth.uid() OR public.is_admin()));

CREATE POLICY "history_insert_operator" ON public.form_fill_history
    FOR INSERT TO authenticated
    WITH CHECK (company_id = public.get_user_company_id() AND operator_user_id = auth.uid());

-- NO UPDATE OR DELETE policies on form_fill_history -> Enforces append-only immutable audit log!

-- ==============================================================================
-- 6. Storage Buckets & Storage Policies
-- ==============================================================================

-- 6.1 Create Private Buckets
INSERT INTO storage.buckets (id, name, public) 
VALUES 
    ('templates', 'templates', false),
    ('signatures', 'signatures', false),
    ('generated-pdfs', 'generated-pdfs', false)
ON CONFLICT (id) DO UPDATE SET public = false;

-- 6.2 Storage RLS: Templates Bucket ({company_id}/...)
CREATE POLICY "storage_templates_select" ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id = 'templates' AND 
        (storage.foldername(name))[1]::uuid = public.get_user_company_id()
    );

CREATE POLICY "storage_templates_all_admin" ON storage.objects
    FOR ALL TO authenticated
    USING (
        bucket_id = 'templates' AND 
        (storage.foldername(name))[1]::uuid = public.get_user_company_id() AND 
        public.is_admin()
    )
    WITH CHECK (
        bucket_id = 'templates' AND 
        (storage.foldername(name))[1]::uuid = public.get_user_company_id() AND 
        public.is_admin()
    );

-- 6.3 Storage RLS: Signatures Bucket ({company_id}/...)
CREATE POLICY "storage_signatures_select" ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id = 'signatures' AND 
        (storage.foldername(name))[1]::uuid = public.get_user_company_id()
    );

CREATE POLICY "storage_signatures_all_admin" ON storage.objects
    FOR ALL TO authenticated
    USING (
        bucket_id = 'signatures' AND 
        (storage.foldername(name))[1]::uuid = public.get_user_company_id() AND 
        public.is_admin()
    )
    WITH CHECK (
        bucket_id = 'signatures' AND 
        (storage.foldername(name))[1]::uuid = public.get_user_company_id() AND 
        public.is_admin()
    );

-- 6.4 Storage RLS: Generated PDFs Bucket ({company_id}/...)
CREATE POLICY "storage_generated_pdfs_select" ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id = 'generated-pdfs' AND 
        (storage.foldername(name))[1]::uuid = public.get_user_company_id()
    );

CREATE POLICY "storage_generated_pdfs_insert_auth" ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id = 'generated-pdfs' AND 
        (storage.foldername(name))[1]::uuid = public.get_user_company_id()
    );

-- ==============================================================================
-- 7. Roles & Grants Configuration
-- ==============================================================================

-- 7.1 Revoke Public / Anon Access
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, public;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, public;

-- 7.2 Grant Access to Authenticated
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;

-- 7.3 Grant Execute on RPC Helper Functions
GRANT EXECUTE ON FUNCTION public.get_user_company_id() TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_admin() TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_company_commercial_profiles() TO authenticated;
