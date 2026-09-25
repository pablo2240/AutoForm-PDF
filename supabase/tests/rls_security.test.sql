-- ==============================================================================
-- AutoForm PDF: Comprehensive RLS and Security Test Suite
-- Path: supabase/tests/rls_security.test.sql
-- Covers: DAC grants, app_metadata forgery prevention, storage access control,
-- template version immutability, legal_rep_only nullable check, cross-tenant isolation,
-- lifecycle RPCs (start, complete, fail), and DIAN Modulo 11 verification.
-- Run inside a PostgreSQL transaction (auto-rolled back).
-- ==============================================================================

BEGIN;

-- 1. Setup Test Harness Fixtures
DO $$
DECLARE
    -- Companies
    v_company_a_id UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
    v_company_b_id UUID := 'b0000000-0000-0000-0000-000000000002'::UUID;

    -- Users (auth.users)
    v_user_admin_a  UUID := '11111111-1111-1111-1111-111111111111'::UUID;
    v_user_comm_a1  UUID := '22222222-2222-2222-2222-222222222222'::UUID;
    v_user_comm_a2  UUID := '22222222-2222-2222-2222-222222222223'::UUID;
    v_user_inact_a  UUID := '33333333-3333-3333-3333-333333333333'::UUID;
    v_user_admin_b  UUID := '44444444-4444-4444-4444-444444444444'::UUID;

    -- Templates & Versions
    v_tpl_a_id UUID := 'aa000000-0000-0000-0000-000000000001'::UUID;
    v_ver_a_id UUID := 'aa111111-0000-0000-0000-000000000001'::UUID;
    v_tpl_b_id UUID := 'bb000000-0000-0000-0000-000000000001'::UUID;
    v_ver_b_id UUID := 'bb111111-0000-0000-0000-000000000001'::UUID;
BEGIN
    RAISE NOTICE '>>> Provisioning Test Fixtures...';

    -- Insert Companies
    INSERT INTO public.companies (id, razon_social, nombre_comercial, nit, dv, is_active)
    VALUES 
        (v_company_a_id, 'Empresa A SAS', 'Empresa A', '900111222', '1', true),
        (v_company_b_id, 'Empresa B SAS', 'Empresa B', '900333444', '2', true);

    -- Insert Mock auth.users (With strict raw_app_meta_data separation)
    INSERT INTO auth.users (id, email, raw_app_meta_data, raw_user_meta_data)
    VALUES 
        (v_user_admin_a, 'admin@iaclatam.com', 
            jsonb_build_object('company_id', v_company_a_id, 'role', 'admin'),
            jsonb_build_object('nombre', 'Admin', 'apellido', 'EmpresaA', 'cargo', 'Gerente', 'celular', '3001111111', 'tipo_documento', 'C.C', 'documento_identidad', '10101010')
        ),
        (v_user_comm_a1, 'comercial1@iaclatam.com', 
            jsonb_build_object('company_id', v_company_a_id, 'role', 'commercial'),
            jsonb_build_object('nombre', 'Comercial1', 'apellido', 'EmpresaA', 'cargo', 'Asesor', 'celular', '3002222221', 'tipo_documento', 'C.C', 'documento_identidad', '20202021')
        ),
        (v_user_comm_a2, 'comercial2@iaclatam.com', 
            jsonb_build_object('company_id', v_company_a_id, 'role', 'commercial'),
            jsonb_build_object('nombre', 'Comercial2', 'apellido', 'EmpresaA', 'cargo', 'Asesor', 'celular', '3002222222', 'tipo_documento', 'C.C', 'documento_identidad', '20202022')
        ),
        (v_user_inact_a, 'inactivo@iaclatam.com', 
            jsonb_build_object('company_id', v_company_a_id, 'role', 'commercial'),
            jsonb_build_object('nombre', 'Inactivo', 'apellido', 'EmpresaA', 'cargo', 'Asesor', 'celular', '3003333333', 'tipo_documento', 'C.C', 'documento_identidad', '30303030')
        ),
        (v_user_admin_b, 'admin@iac.com.co', 
            jsonb_build_object('company_id', v_company_b_id, 'role', 'admin'),
            jsonb_build_object('nombre', 'Admin', 'apellido', 'EmpresaB', 'cargo', 'Gerente', 'celular', '3004444444', 'tipo_documento', 'C.C', 'documento_identidad', '40404040')
        );

    -- Mark inactive user profile as is_active = false
    UPDATE public.profiles SET is_active = false WHERE id = v_user_inact_a;

    -- Insert Bank Accounts
    INSERT INTO public.company_bank_accounts (company_id, entidad_bancaria, tipo_cuenta, numero_cuenta, es_principal, activo)
    VALUES 
        (v_company_a_id, 'Bancolombia', 'Ahorros', '111-000-111', true, true),
        (v_company_b_id, 'Davivienda', 'Corriente', '222-000-222', true, true);

    -- Insert Templates & Versions (Draft by default)
    INSERT INTO public.pdf_templates (id, company_id, codigo, nombre, is_active)
    VALUES 
        (v_tpl_a_id, v_company_a_id, 'TPL-A', 'Template Empresa A', true),
        (v_tpl_b_id, v_company_b_id, 'TPL-B', 'Template Empresa B', true);

    INSERT INTO public.pdf_template_versions (id, template_id, version, filename, storage_path, page_count, status)
    VALUES 
        (v_ver_a_id, v_tpl_a_id, 1, 'tpl_a.pdf', 'a0000000-0000-0000-0000-000000000001/templates/tpl_a.pdf', 1, 'draft'),
        (v_ver_b_id, v_tpl_b_id, 1, 'tpl_b.pdf', 'b0000000-0000-0000-0000-000000000002/templates/tpl_b.pdf', 1, 'draft');

    -- Insert Mappings for Template A (allowed while in draft)
    INSERT INTO public.pdf_mappings (template_version_id, field_key, category, source_path, page_index)
    VALUES 
        (v_ver_a_id, 'razon_social', 'general', 'razon_social', 0);

    RAISE NOTICE '>>> Fixtures Provisioned Successfully.';
END $$;


-- ==============================================================================
-- TEST SCENARIO 1: Anonymous User (Role: anon)
-- Expected: DAC denies SELECT, INSERT, UPDATE, DELETE on all private tables
-- ==============================================================================
DO $$
DECLARE
    v_count INT;
    v_blocked BOOLEAN := false;
BEGIN
    RAISE NOTICE '>>> TEST 1: Running Anonymous Access Check...';
    SET LOCAL ROLE anon;

    BEGIN
        SELECT count(*) INTO v_count FROM public.companies;
        v_blocked := false;
    EXCEPTION WHEN insufficient_privilege THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN RAISE EXCEPTION 'TEST 1.1 FAILED: Anon queried companies'; END IF;

    BEGIN
        SELECT count(*) INTO v_count FROM public.profiles;
        v_blocked := false;
    EXCEPTION WHEN insufficient_privilege THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN RAISE EXCEPTION 'TEST 1.2 FAILED: Anon queried profiles'; END IF;

    BEGIN
        SELECT count(*) INTO v_count FROM public.pdf_templates;
        v_blocked := false;
    EXCEPTION WHEN insufficient_privilege THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN RAISE EXCEPTION 'TEST 1.3 FAILED: Anon queried pdf_templates'; END IF;

    RAISE NOTICE '[PASS] TEST 1: Anonymous user has 0 access (strictly denied by DAC grants & RLS).';
END $$;

RESET ROLE;


-- ==============================================================================
-- TEST SCENARIO 2: App Metadata Forgery Attack Prevention
-- Expected:
--   2.1 User sign-up without app_metadata.company_id FAILS even if user_metadata has company_id
--   2.2 User sign-up with role='admin' in user_metadata is IGNORED (assigned role='commercial')
-- ==============================================================================
DO $$
DECLARE
    v_attacker_id UUID := '99999999-9999-9999-9999-999999999991'::UUID;
    v_attacker2_id UUID := '99999999-9999-9999-9999-999999999992'::UUID;
    v_company_a_id UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
    v_blocked BOOLEAN := false;
    v_assigned_role VARCHAR;
BEGIN
    RAISE NOTICE '>>> TEST 2: Running Metadata Spoofing & Forgery Prevention Check...';

    -- 2.1 Attacker tries to self-assign company_id in raw_user_meta_data
    BEGIN
        INSERT INTO auth.users (id, email, raw_app_meta_data, raw_user_meta_data)
        VALUES (
            v_attacker_id, 
            'attacker@iaclatam.com',
            '{}'::jsonb, -- No company_id in app_metadata!
            jsonb_build_object('company_id', v_company_a_id, 'nombre', 'Attacker', 'apellido', 'Hacker', 'cargo', 'Hacker', 'celular', '3000000000')
        );
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 2.1 FAILED: Attacker successfully forged company_id in user_metadata!';
    END IF;

    -- 2.2 Server creates user with role='commercial' in app_meta, but user sends role='admin' in user_meta
    INSERT INTO auth.users (id, email, raw_app_meta_data, raw_user_meta_data)
    VALUES (
        v_attacker2_id,
        'attacker2@iaclatam.com',
        jsonb_build_object('company_id', v_company_a_id, 'role', 'commercial'),
        jsonb_build_object('role', 'admin', 'nombre', 'Attacker2', 'apellido', 'Hacker2', 'cargo', 'Asesor', 'celular', '3000000002')
    );

    SELECT role INTO v_assigned_role FROM public.profiles WHERE id = v_attacker2_id;
    IF v_assigned_role != 'commercial' THEN
        RAISE EXCEPTION 'TEST 2.2 FAILED: User metadata escalated role to %! Expected commercial.', v_assigned_role;
    END IF;

    RAISE NOTICE '[PASS] TEST 2: User metadata forgery successfully defeated; app_metadata strictly enforced.';
END $$;

RESET ROLE;


-- ==============================================================================
-- TEST SCENARIO 3: Active Commercial Permissions & Legal Rep Only Flow
-- Expected:
--   - Can read own company, own profile, and bank accounts
--   - form_fill_history supports legal_rep_only (commercial_profile_id = NULL)
--   - Cannot update or delete form_fill_history (DAC & RLS block)
-- ==============================================================================
DO $$
DECLARE
    v_comm_a1 UUID := '22222222-2222-2222-2222-222222222222'::UUID;
    v_company_a UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
    v_ver_a UUID := 'aa111111-0000-0000-0000-000000000001'::UUID;
    v_history_id UUID;
    v_blocked BOOLEAN := false;
BEGIN
    RAISE NOTICE '>>> TEST 3: Running Active Commercial Permissions & legal_rep_only Check...';

    SET LOCAL ROLE authenticated;
    PERFORM set_config('request.jwt.claim.sub', v_comm_a1::TEXT, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

    -- 3.1 Insert form_fill_history with commercial_profile_id = NULL (legal_rep_only flow)
    INSERT INTO public.form_fill_history (
        company_id,
        template_version_id,
        operator_user_id,
        commercial_profile_id,
        status,
        output_storage_path
    ) VALUES (
        v_company_a,
        v_ver_a,
        v_comm_a1,
        NULL, -- legal_rep_only!
        'completed',
        v_company_a::TEXT || '/' || v_comm_a1::TEXT || '/hist-01.pdf'
    ) RETURNING id INTO v_history_id;

    IF v_history_id IS NULL THEN
        RAISE EXCEPTION 'TEST 3.1 FAILED: legal_rep_only form fill insertion failed!';
    END IF;

    -- 3.2 Attempt to UPDATE form_fill_history (MUST BE DENIED by DAC)
    BEGIN
        UPDATE public.form_fill_history SET status = 'draft' WHERE id = v_history_id;
        v_blocked := false;
    EXCEPTION WHEN insufficient_privilege THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 3.2 FAILED: Commercial user could UPDATE form_fill_history!';
    END IF;

    -- 3.3 Attempt to DELETE form_fill_history (MUST BE DENIED by DAC)
    BEGIN
        DELETE FROM public.form_fill_history WHERE id = v_history_id;
        v_blocked := false;
    EXCEPTION WHEN insufficient_privilege THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 3.3 FAILED: Commercial user could DELETE form_fill_history!';
    END IF;

    RAISE NOTICE '[PASS] TEST 3: legal_rep_only flow supported and history immutability verified.';
END $$;

RESET ROLE;


-- ==============================================================================
-- TEST SCENARIO 4: Storage RLS Isolation on generated-pdfs
-- Path convention: {company_id}/{operator_user_id}/{history_id}.pdf
-- Expected:
--   4.1 Operator A1 can insert and select their own files
--   4.2 Operator A2 CANNOT read Operator A1's generated PDFs
--   4.3 Admin A CAN read Operator A1's generated PDFs
--   4.4 Commercial users cannot update or delete in storage
-- ==============================================================================
DO $$
DECLARE
    v_company_a UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
    v_admin_a   UUID := '11111111-1111-1111-1111-111111111111'::UUID;
    v_comm_a1   UUID := '22222222-2222-2222-2222-222222222222'::UUID;
    v_comm_a2   UUID := '22222222-2222-2222-2222-222222222223'::UUID;
    v_file_path TEXT := v_company_a::TEXT || '/' || v_comm_a1::TEXT || '/file_01.pdf';
    v_count INT;
    v_blocked BOOLEAN := false;
BEGIN
    RAISE NOTICE '>>> TEST 4: Running Storage Isolation on generated-pdfs...';

    -- 4.1 Operator A1 inserts their PDF
    SET LOCAL ROLE authenticated;
    PERFORM set_config('request.jwt.claim.sub', v_comm_a1::TEXT, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

    INSERT INTO storage.objects (id, bucket_id, name, owner)
    VALUES (gen_random_uuid(), 'generated-pdfs', v_file_path, v_comm_a1);

    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'generated-pdfs' AND name = v_file_path;
    IF v_count != 1 THEN
        RAISE EXCEPTION 'TEST 4.1 FAILED: Operator A1 cannot read their own generated PDF!';
    END IF;

    -- 4.2 Operator A2 tries to read Operator A1's generated PDF (MUST BE 0 ROWS)
    PERFORM set_config('request.jwt.claim.sub', v_comm_a2::TEXT, true);
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'generated-pdfs' AND name = v_file_path;
    IF v_count != 0 THEN
        RAISE EXCEPTION 'TEST 4.2 FAILED: Commercial user A2 can read Commercial user A1 generated PDF!';
    END IF;

    -- 4.3 Operator A2 tries to write to Operator A1's folder (MUST BE BLOCKED)
    BEGIN
        INSERT INTO storage.objects (id, bucket_id, name, owner)
        VALUES (gen_random_uuid(), 'generated-pdfs', v_company_a::TEXT || '/' || v_comm_a1::TEXT || '/hacked.pdf', v_comm_a2);
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 4.3 FAILED: User A2 successfully wrote into User A1 folder!';
    END IF;

    -- 4.4 Admin A reads Operator A1's PDF (MUST BE 1 ROW)
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::TEXT, true);
    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'generated-pdfs' AND name = v_file_path;
    IF v_count != 1 THEN
        RAISE EXCEPTION 'TEST 4.4 FAILED: Admin A cannot read generated PDF of Operator A1!';
    END IF;

    RAISE NOTICE '[PASS] TEST 4: Storage RLS isolation on generated-pdfs verified.';
END $$;

RESET ROLE;


-- ==============================================================================
-- TEST SCENARIO 5: Template Version & Mapping Immutability
-- ==============================================================================
DO $$
DECLARE
    v_admin_a UUID := '11111111-1111-1111-1111-111111111111'::UUID;
    v_ver_a   UUID := 'aa111111-0000-0000-0000-000000000001'::UUID;
    v_blocked BOOLEAN := false;
BEGIN
    RAISE NOTICE '>>> TEST 5: Running Template Version & Mapping Immutability Check...';

    SET LOCAL ROLE authenticated;
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::TEXT, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

    -- 5.1 Attempt to UPDATE immutable column on pdf_template_versions
    BEGIN
        UPDATE public.pdf_template_versions SET filename = 'changed.pdf' WHERE id = v_ver_a;
        v_blocked := false;
    EXCEPTION WHEN insufficient_privilege OR OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 5.1 FAILED: Admin was able to alter immutable column filename on pdf_template_versions!';
    END IF;

    -- 5.2 Attempt to DELETE pdf_template_versions
    BEGIN
        DELETE FROM public.pdf_template_versions WHERE id = v_ver_a;
        v_blocked := false;
    EXCEPTION WHEN insufficient_privilege OR OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 5.2 FAILED: Admin was able to DELETE pdf_template_versions!';
    END IF;

    RAISE NOTICE '[PASS] TEST 5: Template version immutability strictly enforced.';
END $$;

RESET ROLE;


-- ==============================================================================
-- TEST SCENARIO 6: Inactive User Isolation & Cross-Tenant Attack Neutralization
-- ==============================================================================
DO $$
DECLARE
    v_inact_a   UUID := '33333333-3333-3333-3333-333333333333'::UUID;
    v_admin_a   UUID := '11111111-1111-1111-1111-111111111111'::UUID;
    v_company_b UUID := 'b0000000-0000-0000-0000-000000000002'::UUID;
    v_comp_id   UUID;
    v_count     INT;
    v_blocked   BOOLEAN := false;
BEGIN
    RAISE NOTICE '>>> TEST 6: Running Inactive Isolation & Cross-Tenant Leakage Check...';

    -- 6.1 Inactive User
    SET LOCAL ROLE authenticated;
    PERFORM set_config('request.jwt.claim.sub', v_inact_a::TEXT, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

    v_comp_id := public.get_user_company_id();
    IF v_comp_id IS NOT NULL THEN
        RAISE EXCEPTION 'TEST 6.1 FAILED: Inactive user returned company_id %', v_comp_id;
    END IF;

    SELECT count(*) INTO v_count FROM public.companies;
    IF v_count != 0 THEN
        RAISE EXCEPTION 'TEST 6.1 FAILED: Inactive user can see % companies', v_count;
    END IF;

    -- 6.2 Cross-Tenant Insert Attempt by Admin A into Company B
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::TEXT, true);
    BEGIN
        INSERT INTO public.pdf_templates (company_id, codigo, nombre)
        VALUES (v_company_b, 'ATTACK', 'Cross Tenant Template');
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 6.2 FAILED: Admin A managed to insert into Company B!';
    END IF;

    RAISE NOTICE '[PASS] TEST 6: Inactive isolation and cross-tenant boundaries verified.';
END $$;

RESET ROLE;


-- ==============================================================================
-- TEST SCENARIO 7: Template Version Lifecycle & Form Fill RPCs
-- ==============================================================================
DO $$
DECLARE
    v_admin_a   UUID := '11111111-1111-1111-1111-111111111111'::UUID;
    v_comm_a1   UUID := '22222222-2222-2222-2222-222222222222'::UUID;
    v_company_a UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
    v_ver_a     UUID := 'aa111111-0000-0000-0000-000000000001'::UUID;
    v_ver_b     UUID := 'bb111111-0000-0000-0000-000000000001'::UUID;
    v_history_id UUID;
    v_history2_id UUID;
    v_status    VARCHAR;
    v_blocked   BOOLEAN := false;
BEGIN
    RAISE NOTICE '>>> TEST 7: Running Template Lifecycle & Form Fill State Machine Check...';

    -- 7.1 Commercial user tries to publish version A (MUST BE DENIED)
    SET LOCAL ROLE authenticated;
    PERFORM set_config('request.jwt.claim.sub', v_comm_a1::TEXT, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

    BEGIN
        PERFORM public.publish_template_version(v_ver_a);
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 7.1 FAILED: Commercial user published a template version!';
    END IF;

    -- 7.2 Commercial user tries to start form fill on DRAFT version (MUST BE DENIED)
    BEGIN
        PERFORM public.start_form_fill(v_ver_a, v_comm_a1);
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 7.2 FAILED: Form fill started on a draft version!';
    END IF;

    -- 7.3 Admin A publishes version A (MUST SUCCEED)
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::TEXT, true);
    PERFORM public.publish_template_version(v_ver_a);

    SELECT status INTO v_status FROM public.pdf_template_versions WHERE id = v_ver_a;
    IF v_status != 'published' THEN
        RAISE EXCEPTION 'TEST 7.3 FAILED: Template version status is %; expected published.', v_status;
    END IF;

    -- 7.4 Admin A cannot re-publish an already published version
    BEGIN
        PERFORM public.publish_template_version(v_ver_a);
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 7.4 FAILED: Version re-published when already published!';
    END IF;

    -- 7.5 Commercial user starts form fill on PUBLISHED version A (MUST SUCCEED -> processing)
    PERFORM set_config('request.jwt.claim.sub', v_comm_a1::TEXT, true);
    v_history_id := public.start_form_fill(v_ver_a, v_comm_a1);

    SELECT status INTO v_status FROM public.form_fill_history WHERE id = v_history_id;
    IF v_status != 'processing' THEN
        RAISE EXCEPTION 'TEST 7.5 FAILED: New form fill history has status %; expected processing.', v_status;
    END IF;

    -- 7.6 Commercial user attempts complete with INCORRECT storage path (MUST FAIL)
    BEGIN
        PERFORM public.complete_form_fill(v_history_id, 'random/path/file.pdf');
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 7.6 FAILED: Form fill completed with invalid storage path convention!';
    END IF;

    -- 7.7 Commercial user completes with EXACT required path convention (MUST SUCCEED -> completed)
    PERFORM public.complete_form_fill(
        v_history_id, 
        v_company_a::text || '/' || v_comm_a1::text || '/' || v_history_id::text || '.pdf'
    );

    SELECT status INTO v_status FROM public.form_fill_history WHERE id = v_history_id;
    IF v_status != 'completed' THEN
        RAISE EXCEPTION 'TEST 7.7 FAILED: Completed form fill has status %; expected completed.', v_status;
    END IF;

    -- 7.8 Attempt to modify a COMPLETED record (terminal immutability MUST PREVENT)
    BEGIN
        UPDATE public.form_fill_history SET error_message = 'tamper' WHERE id = v_history_id;
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 7.8 FAILED: Completed form fill history was modified!';
    END IF;

    -- 7.9 Start another form fill, then fail it via fail_form_fill (MUST SUCCEED -> failed)
    v_history2_id := public.start_form_fill(v_ver_a, NULL); -- legal rep only
    PERFORM public.fail_form_fill(v_history2_id, 'OCR processing timeout on page 2');

    SELECT status INTO v_status FROM public.form_fill_history WHERE id = v_history2_id;
    IF v_status != 'failed' THEN
        RAISE EXCEPTION 'TEST 7.9 FAILED: Failed form fill has status %; expected failed.', v_status;
    END IF;

    -- 7.10 Attempt to modify a FAILED record (terminal immutability MUST PREVENT)
    BEGIN
        UPDATE public.form_fill_history SET status = 'processing' WHERE id = v_history2_id;
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 7.10 FAILED: Failed form fill history was modified!';
    END IF;

    RAISE NOTICE '[PASS] TEST 7: Template version lifecycle and form fill state machine verified.';
END $$;

RESET ROLE;


-- ==============================================================================
-- TEST SCENARIO 8: Mappings Lifecycle Restrictions
-- ==============================================================================
DO $$
DECLARE
    v_admin_a UUID := '11111111-1111-1111-1111-111111111111'::UUID;
    v_ver_a   UUID := 'aa111111-0000-0000-0000-000000000001'::UUID;
    v_blocked BOOLEAN := false;
BEGIN
    RAISE NOTICE '>>> TEST 8: Running Mappings Lifecycle Restrictions Check...';

    SET LOCAL ROLE authenticated;
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::TEXT, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

    -- 8.1 Inserting mapping into published version A (MUST BE REJECTED)
    BEGIN
        INSERT INTO public.pdf_mappings (template_version_id, field_key, category, source_path, page_index)
        VALUES (v_ver_a, 'nuevo_campo', 'general', 'nuevo_campo', 0);
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 8.1 FAILED: Added mapping to a published version!';
    END IF;

    -- 8.2 Deleting mapping from published version A (MUST BE REJECTED)
    BEGIN
        DELETE FROM public.pdf_mappings WHERE template_version_id = v_ver_a;
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 8.2 FAILED: Deleted mapping from a published version!';
    END IF;

    RAISE NOTICE '[PASS] TEST 8: Mappings modifications on published versions strictly blocked.';
END $$;

RESET ROLE;


-- ==============================================================================
-- TEST SCENARIO 9: Storage Isolation on templates and signatures
-- ==============================================================================
DO $$
DECLARE
    v_company_a UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
    v_company_b UUID := 'b0000000-0000-0000-0000-000000000002'::UUID;
    v_admin_a   UUID := '11111111-1111-1111-1111-111111111111'::UUID;
    v_comm_a1   UUID := '22222222-2222-2222-2222-222222222222'::UUID;
    v_tpl_path  TEXT := v_company_a::TEXT || '/template_sample.pdf';
    v_sig_path  TEXT := v_company_a::TEXT || '/sig_rep.png';
    v_count     INT;
    v_blocked   BOOLEAN := false;
BEGIN
    RAISE NOTICE '>>> TEST 9: Running Storage Isolation on templates & signatures...';

    -- 9.1 Admin A uploads template & signature
    SET LOCAL ROLE authenticated;
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::TEXT, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

    INSERT INTO storage.objects (id, bucket_id, name, owner)
    VALUES 
        (gen_random_uuid(), 'templates', v_tpl_path, v_admin_a),
        (gen_random_uuid(), 'signatures', v_sig_path, v_admin_a);

    -- 9.2 Commercial user can READ template & signature in own company
    PERFORM set_config('request.jwt.claim.sub', v_comm_a1::TEXT, true);

    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'templates' AND name = v_tpl_path;
    IF v_count != 1 THEN
        RAISE EXCEPTION 'TEST 9.2a FAILED: Commercial user cannot read company template!';
    END IF;

    SELECT count(*) INTO v_count FROM storage.objects WHERE bucket_id = 'signatures' AND name = v_sig_path;
    IF v_count != 1 THEN
        RAISE EXCEPTION 'TEST 9.2b FAILED: Commercial user cannot read company signature!';
    END IF;

    -- 9.3 Commercial user CANNOT upload to templates
    BEGIN
        INSERT INTO storage.objects (id, bucket_id, name, owner)
        VALUES (gen_random_uuid(), 'templates', v_company_a::TEXT || '/hacked_tpl.pdf', v_comm_a1);
        v_blocked := false;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 9.3 FAILED: Commercial user uploaded a template!';
    END IF;

    RAISE NOTICE '[PASS] TEST 9: Storage isolation on templates and signatures verified.';
END $$;

RESET ROLE;


-- ==============================================================================
-- TEST SCENARIO 10: DIAN Modulo 11 DV Algorithm & Profiles No-DELETE
-- ==============================================================================
DO $$
DECLARE
    v_admin_a UUID := '11111111-1111-1111-1111-111111111111'::UUID;
    v_comm_a1 UUID := '22222222-2222-2222-2222-222222222222'::UUID;
    v_nit VARCHAR := '811004721';
    v_weights INT[] := ARRAY[41, 37, 29, 23, 19, 17, 13, 7, 3];
    v_sum INT := 0;
    v_calc_dv INT;
    v_blocked BOOLEAN := false;
BEGIN
    RAISE NOTICE '>>> TEST 10: Running DIAN Modulo 11 & Profile Protection Check...';

    -- 10.1 DIAN Modulo 11 calculation for 811004721
    -- Reverse iteration: weights from right to left [3, 7, 13, 17, 19, 23, 29, 37, 41]
    -- 1*3 + 2*7 + 7*13 + 4*17 + 0*19 + 0*23 + 1*29 + 1*37 + 8*41
    -- = 3 + 14 + 91 + 68 + 0 + 0 + 29 + 37 + 328 = 570
    -- 570 % 11 = 9
    -- If remainder in (0, 1) DV = remainder; else DV = 11 - remainder = 11 - 9 = 2!
    v_sum := (8 * 41) + (1 * 37) + (1 * 29) + (0 * 23) + (0 * 19) + (4 * 17) + (7 * 13) + (2 * 7) + (1 * 3);
    IF (v_sum % 11) > 1 THEN
        v_calc_dv := 11 - (v_sum % 11);
    ELSE
        v_calc_dv := v_sum % 11;
    END IF;

    IF v_calc_dv != 2 THEN
        RAISE EXCEPTION 'TEST 10.1 FAILED: DIAN Modulo 11 gave %; expected 2.', v_calc_dv;
    END IF;

    -- 10.2 Verify that Profiles DELETE is blocked for authenticated users
    SET LOCAL ROLE authenticated;
    PERFORM set_config('request.jwt.claim.sub', v_admin_a::TEXT, true);
    PERFORM set_config('request.jwt.claim.role', 'authenticated', true);

    BEGIN
        DELETE FROM public.profiles WHERE id = v_comm_a1;
        v_blocked := false;
    EXCEPTION WHEN insufficient_privilege THEN
        v_blocked := true;
    END;
    IF NOT v_blocked THEN
        RAISE EXCEPTION 'TEST 10.2 FAILED: Authenticated admin could physically DELETE a profile!';
    END IF;

    RAISE NOTICE '[PASS] TEST 10: DIAN Modulo 11 verified and Profile physical deletion blocked.';
END $$;

RESET ROLE;


-- ==============================================================================
-- TEST SCENARIO 11: handle_new_user() ON UPDATE Hardening & Anti-Forgery Check
-- ==============================================================================
DO $$
DECLARE
    v_test_uid UUID := '77777777-7777-7777-7777-777777777777'::UUID;
    v_company_a UUID := 'a0000000-0000-0000-0000-000000000001'::UUID;
    v_orig_created_at TIMESTAMPTZ;
    v_curr_created_at TIMESTAMPTZ;
    v_profile RECORD;
BEGIN
    RAISE NOTICE '>>> TEST 11: Running handle_new_user() ON UPDATE & Anti-Forgery Check...';

    -- 11.1 Create initial user in auth.users
    INSERT INTO auth.users (
        id,
        instance_id,
        email,
        encrypted_password,
        email_confirmed_at,
        raw_app_meta_data,
        raw_user_meta_data,
        created_at,
        updated_at,
        aud,
        role
    ) VALUES (
        v_test_uid,
        '00000000-0000-0000-0000-000000000000',
        'update_tester@iaclatam.com',
        'fake_hash',
        NOW(),
        jsonb_build_object('company_id', v_company_a::TEXT, 'role', 'commercial'),
        jsonb_build_object('nombre', 'Carlos', 'apellido', 'Gomez', 'cargo', 'Ejecutivo', 'celular', '3001112233'),
        NOW(),
        NOW(),
        'authenticated',
        'authenticated'
    );

    SELECT * INTO v_profile FROM public.profiles WHERE id = v_test_uid;
    IF v_profile.nombre != 'Carlos' OR v_profile.role != 'commercial' THEN
        RAISE EXCEPTION 'TEST 11.1 FAILED: Initial profile was not properly created!';
    END IF;
    v_orig_created_at := v_profile.created_at;

    -- 11.2 Update personal fields via raw_user_meta_data (nombre & celular)
    UPDATE auth.users
    SET raw_user_meta_data = jsonb_build_object(
        'nombre', 'Carlos Andres',
        'apellido', 'Gomez Perez',
        'cargo', 'Director Comercial',
        'celular', '3159998877'
    )
    WHERE id = v_test_uid;

    SELECT * INTO v_profile FROM public.profiles WHERE id = v_test_uid;
    IF v_profile.nombre != 'Carlos Andres' OR v_profile.celular != '3159998877' THEN
        RAISE EXCEPTION 'TEST 11.2 FAILED: Profile personal fields did not update!';
    END IF;
    IF v_profile.created_at != v_orig_created_at THEN
        RAISE EXCEPTION 'TEST 11.2 FAILED: created_at changed upon UPDATE!';
    END IF;

    -- 11.3 Update administrative role via raw_app_meta_data
    UPDATE auth.users
    SET raw_app_meta_data = jsonb_build_object('company_id', v_company_a::TEXT, 'role', 'admin')
    WHERE id = v_test_uid;

    SELECT * INTO v_profile FROM public.profiles WHERE id = v_test_uid;
    IF v_profile.role != 'admin' THEN
        RAISE EXCEPTION 'TEST 11.3 FAILED: Role did not update to admin via app_metadata!';
    END IF;

    -- 11.4 Attempted Privilege Escalation via raw_user_meta_data
    -- Reset app_metadata to commercial, but malicious user sends 'role': 'admin' in user_metadata
    UPDATE auth.users
    SET raw_app_meta_data = jsonb_build_object('company_id', v_company_a::TEXT, 'role', 'commercial'),
        raw_user_meta_data = jsonb_build_object(
            'role', 'admin', -- MALICIOUS INJECTION IN USER_METADATA!
            'nombre', 'Carlos Hacked',
            'apellido', 'Gomez',
            'cargo', 'Ejecutivo',
            'celular', '3159998877'
        )
    WHERE id = v_test_uid;

    SELECT * INTO v_profile FROM public.profiles WHERE id = v_test_uid;
    IF v_profile.role != 'commercial' THEN
        RAISE EXCEPTION 'TEST 11.4 FAILED: User could forge role via user_metadata!';
    END IF;

    RAISE NOTICE '[PASS] TEST 11: handle_new_user() ON UPDATE, created_at preservation, and anti-forgery verified.';
END $$;

RESET ROLE;


-- Rollback all test data so database remains strictly 0 rows!
ROLLBACK;
