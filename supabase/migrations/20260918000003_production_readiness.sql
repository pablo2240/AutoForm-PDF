-- ============================================================================
-- AutoForm PDF: Production Readiness & Hardening Migration
-- Migration: 20260918000003_production_readiness.sql
--
-- 1. Eliminación de capacidades destructivas en producción:
--    Remueve permanentemente public.admin_reset_test_environment()
-- 2. Idempotencia y seguridad en handle_new_user() sobre UPDATE:
--    Utiliza INSERT ... ON CONFLICT (id) DO UPDATE SET.
--    company_id y role provienen EXCLUSIVAMENTE de raw_app_meta_data.
--    Campos personales se sincronizan desde raw_user_meta_data.
--    created_at se preserva intacto; updated_at se actualiza a NOW().
--    Inmune a manipulación de role o company_id desde user_metadata.
-- ============================================================================

-- 1. Eliminar función destructiva de pruebas en producción
DROP FUNCTION IF EXISTS public.admin_reset_test_environment();

-- 2. Actualizar función handle_new_user() con soporte endurecido para UPDATE
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
    v_existing_profile RECORD;
BEGIN
    -- 1. Consultar si ya existe perfil para el usuario
    SELECT * INTO v_existing_profile FROM public.profiles WHERE id = NEW.id;

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
        -- Conservar company_id existente en UPDATE si no se proveyó uno nuevo en app_metadata
        v_company_id := v_existing_profile.company_id;
    ELSE
        -- Si es INSERT inicial sin app_metadata (fase inicial de GoTrue), permitir que complete
        IF TG_OP = 'INSERT' THEN
            RETURN NEW;
        END IF;
        RAISE EXCEPTION 'Cannot register user: company_id is required in app_metadata (server-side only)';
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
        -- Conservar role existente en UPDATE si no se proveyó uno nuevo en app_metadata
        v_role := v_existing_profile.role;
    ELSE
        v_role := 'commercial';
    END IF;

    -- 5. Extraer atributos personales permitidos desde raw_user_meta_data
    v_nombre := TRIM(COALESCE(NEW.raw_user_meta_data->>'nombre', ''));
    v_apellido := TRIM(COALESCE(NEW.raw_user_meta_data->>'apellido', ''));
    v_cargo := TRIM(COALESCE(NEW.raw_user_meta_data->>'cargo', ''));
    v_celular := TRIM(COALESCE(NEW.raw_user_meta_data->>'celular', ''));
    v_tipo_doc := COALESCE(NEW.raw_user_meta_data->>'tipo_documento', 'C.C');
    v_doc_id := NEW.raw_user_meta_data->>'documento_identidad';

    -- Si es nuevo registro, exigir completitud de perfil
    IF v_existing_profile.id IS NULL THEN
        IF char_length(v_nombre) < 2 OR char_length(v_apellido) < 2 OR char_length(v_cargo) < 2 OR char_length(v_celular) < 5 THEN
            -- Si la fase GoTrue inicial no trae los campos, retornar NEW para esperar el UPDATE con metadatos completos
            IF TG_OP = 'INSERT' AND NEW.raw_app_meta_data->>'company_id' IS NULL THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'Cannot register user: missing or invalid profile attributes (nombre, apellido, cargo, celular)';
        END IF;
    END IF;

    -- 6. Inserción o actualización idempotente (evita PK conflicts y preserva created_at)
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
        NOW(),
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        -- company_id y role SOLO cambian si vienen en raw_app_meta_data
        company_id = COALESCE(v_company_id, public.profiles.company_id),
        role = COALESCE(v_role, public.profiles.role),
        email = LOWER(NEW.email),
        nombre = CASE WHEN char_length(v_nombre) >= 2 THEN v_nombre ELSE public.profiles.nombre END,
        apellido = CASE WHEN char_length(v_apellido) >= 2 THEN v_apellido ELSE public.profiles.apellido END,
        display_name = CASE 
            WHEN char_length(v_nombre) >= 2 AND char_length(v_apellido) >= 2 THEN TRIM(v_nombre || ' ' || v_apellido)
            WHEN char_length(v_nombre) >= 2 THEN TRIM(v_nombre || ' ' || public.profiles.apellido)
            WHEN char_length(v_apellido) >= 2 THEN TRIM(public.profiles.nombre || ' ' || v_apellido)
            ELSE public.profiles.display_name
        END,
        cargo = CASE WHEN char_length(v_cargo) >= 2 THEN v_cargo ELSE public.profiles.cargo END,
        celular = CASE WHEN char_length(v_celular) >= 5 THEN v_celular ELSE public.profiles.celular END,
        tipo_documento = COALESCE(v_tipo_doc, public.profiles.tipo_documento),
        documento_identidad = COALESCE(v_doc_id, public.profiles.documento_identidad),
        -- created_at queda 100% INTACTO
        updated_at = NOW();

    RETURN NEW;
END;
$$;
