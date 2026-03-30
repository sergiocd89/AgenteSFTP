-- 03_postgresql_18_3_profile_admin_procedures.sql
-- Objetivo: procedimientos de administración de usuarios/perfiles para el panel.

BEGIN;

CREATE OR REPLACE PROCEDURE app_auth.sp_create_user_profile(
    IN p_username VARCHAR,
    IN p_plain_password VARCHAR,
    IN p_full_name VARCHAR DEFAULT NULL,
    IN p_is_admin BOOLEAN DEFAULT FALSE,
    IN p_is_active BOOLEAN DEFAULT TRUE,
    IN p_modules TEXT[] DEFAULT ARRAY[]::TEXT[],
    IN p_actor VARCHAR DEFAULT 'profile-admin'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id BIGINT;
    v_invalid_modules TEXT;
BEGIN
    IF COALESCE(TRIM(p_username), '') = '' THEN
        RAISE EXCEPTION 'username es requerido';
    END IF;

    IF COALESCE(TRIM(p_plain_password), '') = '' THEN
        RAISE EXCEPTION 'password es requerido';
    END IF;

    CALL app_auth.sp_create_user(
        p_username,
        p_plain_password,
        p_full_name,
        p_is_admin,
        p_is_active,
        p_actor
    );

    SELECT u.id
      INTO v_user_id
      FROM app_auth.app_user u
     WHERE u.username = TRIM(p_username);

    IF NOT FOUND THEN
        RAISE EXCEPTION 'no se pudo recuperar user_id para %', p_username;
    END IF;

    DELETE FROM app_auth.user_module
     WHERE user_id = v_user_id;

    SELECT string_agg(m.module_key, ', ')
      INTO v_invalid_modules
      FROM (
            SELECT DISTINCT TRIM(x)::TEXT AS module_key
              FROM unnest(COALESCE(p_modules, ARRAY[]::TEXT[])) AS x
             WHERE COALESCE(TRIM(x), '') <> ''
           ) m
 LEFT JOIN app_auth.profile_module pm
        ON pm.module_key = m.module_key
       AND pm.is_active = TRUE
     WHERE pm.module_key IS NULL;

    IF v_invalid_modules IS NOT NULL THEN
        RAISE EXCEPTION 'modulos invalidos o inactivos: %', v_invalid_modules;
    END IF;

    INSERT INTO app_auth.user_module (user_id, module_key, granted_by)
    SELECT
        v_user_id,
        m.module_key,
        p_actor
    FROM (
        SELECT DISTINCT TRIM(x)::TEXT AS module_key
        FROM unnest(COALESCE(p_modules, ARRAY[]::TEXT[])) AS x
        WHERE COALESCE(TRIM(x), '') <> ''
    ) m
    ON CONFLICT (user_id, module_key) DO NOTHING;
END;
$$;

CREATE OR REPLACE PROCEDURE app_auth.sp_update_user_profile(
    IN p_username VARCHAR,
    IN p_full_name VARCHAR DEFAULT NULL,
    IN p_is_admin BOOLEAN DEFAULT NULL,
    IN p_is_active BOOLEAN DEFAULT NULL,
    IN p_modules TEXT[] DEFAULT NULL,
    IN p_actor VARCHAR DEFAULT 'profile-admin'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id BIGINT;
    v_invalid_modules TEXT;
BEGIN
    IF COALESCE(TRIM(p_username), '') = '' THEN
        RAISE EXCEPTION 'username es requerido';
    END IF;

    SELECT u.id
      INTO v_user_id
      FROM app_auth.app_user u
     WHERE u.username = TRIM(p_username);

    IF NOT FOUND THEN
        RAISE EXCEPTION 'usuario no existe: %', p_username;
    END IF;

    UPDATE app_auth.app_user
       SET full_name  = COALESCE(NULLIF(TRIM(p_full_name), ''), full_name),
           is_admin   = COALESCE(p_is_admin, is_admin),
           is_active  = COALESCE(p_is_active, is_active),
           updated_by = p_actor,
           updated_at = NOW()
     WHERE id = v_user_id;

    IF p_modules IS NOT NULL THEN
        SELECT string_agg(m.module_key, ', ')
          INTO v_invalid_modules
          FROM (
                SELECT DISTINCT TRIM(x)::TEXT AS module_key
                  FROM unnest(COALESCE(p_modules, ARRAY[]::TEXT[])) AS x
                 WHERE COALESCE(TRIM(x), '') <> ''
               ) m
     LEFT JOIN app_auth.profile_module pm
            ON pm.module_key = m.module_key
           AND pm.is_active = TRUE
         WHERE pm.module_key IS NULL;

        IF v_invalid_modules IS NOT NULL THEN
            RAISE EXCEPTION 'modulos invalidos o inactivos: %', v_invalid_modules;
        END IF;

        DELETE FROM app_auth.user_module
         WHERE user_id = v_user_id;

        INSERT INTO app_auth.user_module (user_id, module_key, granted_by)
        SELECT
            v_user_id,
            m.module_key,
            p_actor
        FROM (
            SELECT DISTINCT TRIM(x)::TEXT AS module_key
            FROM unnest(COALESCE(p_modules, ARRAY[]::TEXT[])) AS x
            WHERE COALESCE(TRIM(x), '') <> ''
        ) m
        ON CONFLICT (user_id, module_key) DO NOTHING;
    END IF;
END;
$$;

CREATE OR REPLACE PROCEDURE app_auth.sp_admin_reset_password(
    IN p_username VARCHAR,
    IN p_new_plain_password VARCHAR,
    IN p_actor VARCHAR DEFAULT 'profile-admin'
)
LANGUAGE plpgsql
AS $$
BEGIN
    CALL app_auth.sp_change_password(p_username, p_new_plain_password, p_actor);
END;
$$;

CREATE OR REPLACE PROCEDURE app_auth.sp_deactivate_user(
    IN p_username VARCHAR,
    IN p_actor VARCHAR DEFAULT 'profile-admin'
)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE app_auth.app_user
       SET is_active = FALSE,
           updated_by = p_actor,
           updated_at = NOW()
     WHERE username = TRIM(COALESCE(p_username, ''));

    IF NOT FOUND THEN
        RAISE EXCEPTION 'usuario no existe: %', p_username;
    END IF;
END;
$$;

COMMIT;
