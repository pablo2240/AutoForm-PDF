-- Migration: 20261001000000_user_documents_isolation_and_slot.sql
-- Description: ADR-0011 Cross-Account Data Isolation and User-Scoped Workspace Storage
-- Target Project: tnhedxwbpqihlqbtzudt

-- 1. Tabla relacional user_documents
CREATE TABLE IF NOT EXISTS public.user_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    template_code VARCHAR(100),
    filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    size_kb NUMERIC(10, 1),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Índices (Garantía de Ranura Única en BD + Lookup de alta frecuencia)
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_documents_single_active
ON public.user_documents(user_id)
WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_user_documents_user_active
ON public.user_documents(user_id, is_active)
WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_user_documents_company
ON public.user_documents(company_id);

-- 3. Trigger para updated_at (reutilizando public.set_updated_at() existente sin redefinir)
DROP TRIGGER IF EXISTS trg_user_documents_updated_at ON public.user_documents;
CREATE TRIGGER trg_user_documents_updated_at
    BEFORE UPDATE ON public.user_documents
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- 4. Row Level Security (RLS)
ALTER TABLE public.user_documents ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_documents_select_isolation" ON public.user_documents;
CREATE POLICY "user_documents_select_isolation" ON public.user_documents
    FOR SELECT TO authenticated
    USING (
        company_id = public.get_user_company_id()
        AND (user_id = auth.uid() OR public.is_admin())
    );

DROP POLICY IF EXISTS "user_documents_insert_own" ON public.user_documents;
CREATE POLICY "user_documents_insert_own" ON public.user_documents
    FOR INSERT TO authenticated
    WITH CHECK (
        company_id = public.get_user_company_id()
        AND user_id = auth.uid()
    );

DROP POLICY IF EXISTS "user_documents_update_own" ON public.user_documents;
CREATE POLICY "user_documents_update_own" ON public.user_documents
    FOR UPDATE TO authenticated
    USING (
        company_id = public.get_user_company_id()
        AND (user_id = auth.uid() OR public.is_admin())
    )
    WITH CHECK (
        company_id = public.get_user_company_id()
        AND (user_id = auth.uid() OR public.is_admin())
    );

DROP POLICY IF EXISTS "user_documents_delete_own_or_admin" ON public.user_documents;
CREATE POLICY "user_documents_delete_own_or_admin" ON public.user_documents
    FOR DELETE TO authenticated
    USING (
        company_id = public.get_user_company_id()
        AND (user_id = auth.uid() OR public.is_admin())
    );

-- 5. Función de auditoría de referencias cruzadas para purga condicionada
CREATE OR REPLACE FUNCTION public.can_hard_delete_user_document(p_doc_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_doc RECORD;
BEGIN
    SELECT * INTO v_doc FROM public.user_documents WHERE id = p_doc_id;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Auditoría de referencias en form_fill_history (metadatos o storage_path)
    IF EXISTS (
        SELECT 1 FROM public.form_fill_history
        WHERE (metadata->>'user_document_id') = p_doc_id::text
           OR (metadata->>'source_storage_path') = v_doc.storage_path
    ) THEN
        RETURN FALSE;
    END IF;

    RETURN TRUE;
END;
$$;

GRANT EXECUTE ON FUNCTION public.can_hard_delete_user_document(UUID) TO authenticated;
