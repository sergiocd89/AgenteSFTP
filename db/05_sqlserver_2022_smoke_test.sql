-- 05_sqlserver_2022_smoke_test.sql
-- Objetivo: validar instalación desde cero.

SELECT 'users' AS check_name, COUNT(*) AS total FROM app_auth.app_user
UNION ALL
SELECT 'modules' AS check_name, COUNT(*) AS total FROM app_auth.profile_module
UNION ALL
SELECT 'user_module' AS check_name, COUNT(*) AS total FROM app_auth.user_module;
GO

SELECT username, is_admin, is_active
FROM app_auth.app_user
WHERE username = N'admin';
GO

EXEC app_auth.sp_get_user_modules @username = N'admin';
GO

SELECT app_auth.fn_is_admin(N'admin') AS admin_is_admin;
GO

EXEC app_auth.sp_validate_login
    @username = N'admin',
    @password = N'Admin#2026',
    @client_ip = NULL,
    @user_agent = N'smoke-test';
GO
