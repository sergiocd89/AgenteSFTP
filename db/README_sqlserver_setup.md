# SQL Server 2022 Setup Desde Cero

Ejecuta los scripts en este orden exacto:

1. `01_sqlserver_2022_auth_base.sql`
2. `02_sqlserver_2022_profiles_base.sql`
3. `03_sqlserver_2022_profile_admin_procedures.sql`
4. `04_sqlserver_2022_seed_admin_all_modules.sql`
5. `05_sqlserver_2022_smoke_test.sql` (validación)

## Resultado Esperado

- Base funcional para login y administración de perfiles.
- Usuario bootstrap administrador:
  - `username`: `admin`
  - `password`: `Admin#2026`
  - `is_admin`: `1`
  - acceso a todos los módulos activos.

## Notas

- Los scripts usan `CREATE OR ALTER` e `IF OBJECT_ID ... IS NULL` para ser seguros en re-ejecución.
- Ejecuta en la misma base de datos objetivo.
- Si quieres ajustar el password inicial de admin, modifica el archivo `04_sqlserver_2022_seed_admin_all_modules.sql`.
