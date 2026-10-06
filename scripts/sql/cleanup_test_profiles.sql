-- Limpieza de cuentas de prueba creadas por pruebas automáticas (test_sync_*, test_access_*).
-- Ejecutar a mano en el SQL Editor de Supabase del proyecto a limpiar. Paso 1 = solo lectura.

-- PASO 1 (revisión): debe listar SOLO cuentas de prueba y sin dependencias.
select p.id, p.email, p.created_at,
       (select count(*) from public.form_fill_history h where h.operator_user_id = p.id or h.commercial_profile_id = p.id) as historial,
       (select count(*) from public.user_documents d where d.user_id = p.id) as documentos,
       (select count(*) from public.legal_representatives l where l.user_id = p.id) as representantes
from public.profiles p
where p.email ~ '^test_(sync_emp|sync_comm|access_created|access_unpriv)_[0-9a-f]{6}@iaclatam\.com$'
order by p.created_at;

-- PASO 2 (borrado): solo si el paso 1 mostró únicamente cuentas de prueba con 0 dependencias.
begin;
with t as (
  select id from public.profiles
  where email ~ '^test_(sync_emp|sync_comm|access_created|access_unpriv)_[0-9a-f]{6}@iaclatam\.com$'
    and role = 'commercial'
), dp as (delete from public.profiles where id in (select id from t) returning id),
   du as (delete from auth.users    where id in (select id from t) returning id)
select (select count(*) from dp) as perfiles_borrados, (select count(*) from du) as usuarios_auth_borrados;
-- Verificar las cifras (esperado en producción hoy: 22 y 22) y confirmar con COMMIT; (o ROLLBACK;).
commit;

-- PASO 3 (comprobación): no debe quedar ninguna cuenta de prueba.
select count(*) as pruebas_restantes from public.profiles where email ilike 'test\_%';

-- Si usas Neon (public.commercial_profiles), el mismo patrón sobre la columna email:
-- delete from public.commercial_profiles where email ~ '^test_(sync_emp|sync_comm|access_created|access_unpriv)_[0-9a-f]{6}@iaclatam\.com$';
