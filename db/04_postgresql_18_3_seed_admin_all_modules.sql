-- 04_postgresql_18_3_seed_admin_all_modules.sql
-- Objetivo: dejar un admin funcional con acceso a todos los módulos activos.

BEGIN;

-- Crea/actualiza usuario administrador bootstrap
CALL app_auth.sp_create_user(
    p_username => 'admin',
    p_plain_password => 'Admin#2026',
    p_full_name => 'Administrador',
    p_is_admin => TRUE,
    p_is_active => TRUE,
    p_actor => 'bootstrap'
);

-- Reemplaza permisos por todos los módulos activos
DELETE FROM app_auth.user_module um
USING app_auth.app_user u
WHERE um.user_id = u.id
  AND u.username = 'admin';

INSERT INTO app_auth.user_module (user_id, module_key, granted_by)
SELECT u.id, pm.module_key, 'bootstrap'
FROM app_auth.app_user u
JOIN app_auth.profile_module pm ON pm.is_active = TRUE
WHERE u.username = 'admin'
ON CONFLICT (user_id, module_key) DO NOTHING;

COMMIT;
