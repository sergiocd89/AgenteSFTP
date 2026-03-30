-- 04_sqlserver_2022_seed_admin_all_modules.sql
-- Objetivo: crear/actualizar admin y asignarle todos los módulos activos.

EXEC app_auth.sp_create_user
    @username = N'admin',
    @plain_password = N'Admin#2026',
    @full_name = N'Administrador',
    @is_admin = 1,
    @is_active = 1,
    @actor = N'bootstrap';
GO

DECLARE @admin_id BIGINT;
SELECT @admin_id = id FROM app_auth.app_user WHERE username = N'admin';

DELETE FROM app_auth.user_module WHERE user_id = @admin_id;

INSERT INTO app_auth.user_module (user_id, module_key, granted_by)
SELECT @admin_id, pm.module_key, N'bootstrap'
FROM app_auth.profile_module pm
WHERE pm.is_active = 1;
GO
