# PostgreSQL Setup Desde Cero

Ejecuta los scripts en este orden exacto:

1. `01_postgresql_18_3_auth_base.sql`
2. `02_postgresql_18_3_profiles_base.sql`
3. `03_postgresql_18_3_profile_admin_procedures.sql`
4. `04_postgresql_18_3_seed_admin_all_modules.sql`
5. `05_postgresql_18_3_smoke_test.sql` (validación)

## Resultado Esperado

- Base funcional para login y administración de perfiles.
- Usuario administrador bootstrap:
  - `username`: `admin`
  - `password`: `Admin#2026`
  - `is_admin`: `true`
  - Acceso a **todos** los módulos activos.

## Ejecución rápida en psql

```sql
\i db/01_postgresql_18_3_auth_base.sql
\i db/02_postgresql_18_3_profiles_base.sql
\i db/03_postgresql_18_3_profile_admin_procedures.sql
\i db/04_postgresql_18_3_seed_admin_all_modules.sql
\i db/05_postgresql_18_3_smoke_test.sql
```

## Notas

- Los scripts son idempotentes en lo principal (`CREATE ... IF NOT EXISTS`, `CREATE OR REPLACE`, `ON CONFLICT`).
- Si aparece `25P02` en una sesión, ejecuta `ROLLBACK;` y corre nuevamente el script que falló.
- Los scripts legacy anteriores se mantienen para compatibilidad, pero para instalación nueva usa este flujo numerado.
