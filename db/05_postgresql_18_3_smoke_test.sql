-- 05_postgresql_18_3_smoke_test.sql
-- Objetivo: validar que la base quedó funcional tras ejecutar 01..04.

SELECT 'users' AS check_name, COUNT(*) AS total
FROM app_auth.app_user
UNION ALL
SELECT 'modules' AS check_name, COUNT(*) AS total
FROM app_auth.profile_module
UNION ALL
SELECT 'user_module' AS check_name, COUNT(*) AS total
FROM app_auth.user_module;

SELECT u.username, u.is_admin, u.is_active
FROM app_auth.app_user u
WHERE u.username = 'admin';

SELECT *
FROM app_auth.fn_get_user_modules('admin');

SELECT app_auth.fn_is_admin('admin') AS admin_is_admin;

SELECT *
FROM app_auth.sp_validate_login('admin', 'Admin#2026', NULL, 'smoke-test');
