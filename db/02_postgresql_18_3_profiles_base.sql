-- 02_postgresql_18_3_profiles_base.sql
-- Objetivo: crear catálogo de módulos, permisos por usuario y SPs básicos de perfiles.

BEGIN;

CREATE SCHEMA IF NOT EXISTS app_auth;

CREATE TABLE IF NOT EXISTS app_auth.profile_module (
    module_key VARCHAR(80) PRIMARY KEY,
    module_label VARCHAR(120) NOT NULL,
    app_mode VARCHAR(80) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS app_auth.user_module (
    user_id BIGINT NOT NULL REFERENCES app_auth.app_user(id) ON DELETE CASCADE,
    module_key VARCHAR(80) NOT NULL REFERENCES app_auth.profile_module(module_key),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by VARCHAR(100),
    PRIMARY KEY (user_id, module_key)
);

CREATE INDEX IF NOT EXISTS idx_user_module_user_id ON app_auth.user_module (user_id);
CREATE INDEX IF NOT EXISTS idx_user_module_module_key ON app_auth.user_module (module_key);

CREATE OR REPLACE FUNCTION app_auth.set_profile_module_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_profile_module_updated_at ON app_auth.profile_module;

CREATE TRIGGER trg_profile_module_updated_at
BEFORE UPDATE ON app_auth.profile_module
FOR EACH ROW
EXECUTE FUNCTION app_auth.set_profile_module_updated_at();

CREATE OR REPLACE PROCEDURE app_auth.sp_grant_module_to_user(
    IN p_username VARCHAR,
    IN p_module_key VARCHAR,
    IN p_actor VARCHAR DEFAULT 'system'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id BIGINT;
BEGIN
    SELECT id
      INTO v_user_id
      FROM app_auth.app_user
     WHERE username = TRIM(COALESCE(p_username, ''))
       AND is_active = TRUE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'usuario no existe o está inactivo: %', p_username;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM app_auth.profile_module
         WHERE module_key = TRIM(COALESCE(p_module_key, ''))
           AND is_active = TRUE
    ) THEN
        RAISE EXCEPTION 'módulo no existe o está inactivo: %', p_module_key;
    END IF;

    INSERT INTO app_auth.user_module (user_id, module_key, granted_by)
    VALUES (v_user_id, TRIM(p_module_key), p_actor)
    ON CONFLICT (user_id, module_key) DO NOTHING;
END;
$$;

CREATE OR REPLACE PROCEDURE app_auth.sp_revoke_module_from_user(
    IN p_username VARCHAR,
    IN p_module_key VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id BIGINT;
BEGIN
    SELECT id
      INTO v_user_id
      FROM app_auth.app_user
     WHERE username = TRIM(COALESCE(p_username, ''));

    IF NOT FOUND THEN
        RAISE EXCEPTION 'usuario no existe: %', p_username;
    END IF;

    DELETE
      FROM app_auth.user_module
     WHERE user_id = v_user_id
       AND module_key = TRIM(COALESCE(p_module_key, ''));
END;
$$;

CREATE OR REPLACE FUNCTION app_auth.fn_get_user_modules(
    p_username VARCHAR
)
RETURNS TABLE (module_key VARCHAR)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT um.module_key
      FROM app_auth.app_user u
      JOIN app_auth.user_module um ON um.user_id = u.id
      JOIN app_auth.profile_module pm ON pm.module_key = um.module_key
     WHERE u.username = TRIM(COALESCE(p_username, ''))
       AND u.is_active = TRUE
       AND pm.is_active = TRUE
     ORDER BY um.module_key;
END;
$$;

CREATE OR REPLACE FUNCTION app_auth.fn_is_admin(
    p_username VARCHAR
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    v_is_admin BOOLEAN;
BEGIN
    SELECT is_admin
      INTO v_is_admin
      FROM app_auth.app_user
     WHERE username = TRIM(COALESCE(p_username, ''))
       AND is_active = TRUE;

    RETURN COALESCE(v_is_admin, FALSE);
END;
$$;

INSERT INTO app_auth.profile_module (module_key, module_label, app_mode, created_by, updated_by)
VALUES
    ('SFTP', '🔐 FTP ➔ SFTP', 'SFTP_Module', 'bootstrap', 'bootstrap'),
    ('COBOL', '🐍 COBOL ➔ Python', 'COBOL_Module', 'bootstrap', 'bootstrap'),
    ('DTSX', '📦 COBOL ➔ DTSX', 'DTSX_Module', 'bootstrap', 'bootstrap'),
    ('RequirementWorkflow', '🧩 Requirement Workflow', 'Requirement_Workflow_Module', 'bootstrap', 'bootstrap'),
    ('Documentation', '📝 Documentación', 'Documentation_Module', 'bootstrap', 'bootstrap')
ON CONFLICT (module_key)
DO UPDATE SET
    module_label = EXCLUDED.module_label,
    app_mode = EXCLUDED.app_mode,
    is_active = TRUE,
    updated_by = EXCLUDED.updated_by,
    updated_at = NOW();

COMMIT;
