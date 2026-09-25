-- ==============================================================================
-- AutoForm PDF (SmartFormAI) - Versioned Migration
-- Migration: 20260925010000_ensure_case_insensitive_email_unique.sql
-- Enforces case-insensitive uniqueness on email for public.profiles
-- ==============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS uq_profiles_email_lower ON public.profiles (LOWER(email));
