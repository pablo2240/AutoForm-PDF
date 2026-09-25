-- Migration: 20260925000000_add_ciudad_to_profiles.sql
-- Description: Non-disruptive addition of ciudad column to public.profiles.
-- Existing records remain valid with NULL/empty ciudad until updated;
-- all new commercial registrations enforce ciudad at application level.

ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS ciudad VARCHAR(100);

COMMENT ON COLUMN public.profiles.ciudad IS 'Ciudad de residencia u operacion del perfil comercial';
