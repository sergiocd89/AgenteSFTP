-- 01_postgresql_18_3_auth_base.sql
-- Objetivo: crear base de autenticación desde cero (schema, tablas, funciones y SPs).

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE SCHEMA IF NOT EXISTS app_auth;

CREATE TABLE IF NOT EXISTS app_auth.app_user (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username CITEXT NOT NULL UNIQUE,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(200),
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    failed_attempts INT NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS app_auth.auth_login_attempt (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT REFERENCES app_auth.app_user(id),
    username_input VARCHAR(150) NOT NULL,
    is_success BOOLEAN NOT NULL,
    reason_code VARCHAR(40) NOT NULL,
    client_ip INET,
    user_agent TEXT,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_login_attempt_attempted_at
    ON app_auth.auth_login_attempt (attempted_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_login_attempt_username_input
    ON app_auth.auth_login_attempt (username_input);

CREATE OR REPLACE FUNCTION app_auth.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_app_user_updated_at ON app_auth.app_user;

CREATE TRIGGER trg_app_user_updated_at
BEFORE UPDATE ON app_auth.app_user
FOR EACH ROW
EXECUTE FUNCTION app_auth.set_updated_at();

CREATE OR REPLACE PROCEDURE app_auth.sp_create_user(
    IN p_username VARCHAR,
    IN p_plain_password VARCHAR,
    IN p_full_name VARCHAR DEFAULT NULL,
    IN p_is_admin BOOLEAN DEFAULT FALSE,
    IN p_is_active BOOLEAN DEFAULT TRUE,
    IN p_actor VARCHAR DEFAULT 'system'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_salt TEXT;
BEGIN
    IF COALESCE(TRIM(p_username), '') = '' THEN
        RAISE EXCEPTION 'username es requerido';
    END IF;

    IF COALESCE(TRIM(p_plain_password), '') = '' THEN
        RAISE EXCEPTION 'password es requerido';
    END IF;

    v_salt := encode(gen_random_bytes(16), 'hex');

    INSERT INTO app_auth.app_user (
        username,
        password_salt,
        password_hash,
        full_name,
        is_admin,
        is_active,
        created_by,
        updated_by
    )
    VALUES (
        TRIM(p_username),
        v_salt,
        encode(digest(p_plain_password || v_salt, 'sha256'), 'hex'),
        NULLIF(TRIM(p_full_name), ''),
        p_is_admin,
        p_is_active,
        p_actor,
        p_actor
    )
    ON CONFLICT (username)
    DO UPDATE
    SET
        password_salt = EXCLUDED.password_salt,
        password_hash = EXCLUDED.password_hash,
        full_name = EXCLUDED.full_name,
        is_admin = EXCLUDED.is_admin,
        is_active = EXCLUDED.is_active,
        updated_by = EXCLUDED.updated_by,
        updated_at = NOW();
END;
$$;

CREATE OR REPLACE PROCEDURE app_auth.sp_change_password(
    IN p_username VARCHAR,
    IN p_new_plain_password VARCHAR,
    IN p_actor VARCHAR DEFAULT 'system'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_salt TEXT;
BEGIN
    IF COALESCE(TRIM(p_username), '') = '' THEN
        RAISE EXCEPTION 'username es requerido';
    END IF;

    IF COALESCE(TRIM(p_new_plain_password), '') = '' THEN
        RAISE EXCEPTION 'new password es requerido';
    END IF;

    v_salt := encode(gen_random_bytes(16), 'hex');

    UPDATE app_auth.app_user
    SET
        password_salt = v_salt,
        password_hash = encode(digest(p_new_plain_password || v_salt, 'sha256'), 'hex'),
        failed_attempts = 0,
        locked_until = NULL,
        updated_by = p_actor,
        updated_at = NOW()
    WHERE username = TRIM(p_username);

    IF NOT FOUND THEN
        RAISE EXCEPTION 'usuario no existe: %', p_username;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION app_auth.sp_validate_login(
    p_username VARCHAR,
    p_password VARCHAR,
    p_client_ip INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
)
RETURNS TABLE (
    auth_ok BOOLEAN,
    user_id BIGINT,
    username VARCHAR,
    reason_code VARCHAR,
    message VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_user app_auth.app_user%ROWTYPE;
    v_password_ok BOOLEAN := FALSE;
    v_reason_code VARCHAR(40);
    v_message VARCHAR(200);
BEGIN
    SELECT au.*
      INTO v_user
      FROM app_auth.app_user AS au
     WHERE au.username = TRIM(COALESCE(p_username, ''));

    IF NOT FOUND THEN
        v_reason_code := 'USER_NOT_FOUND';
        v_message := 'Usuario o contraseña inválidos.';

        INSERT INTO app_auth.auth_login_attempt (
            user_id, username_input, is_success, reason_code, client_ip, user_agent
        ) VALUES (
            NULL, COALESCE(p_username, ''), FALSE, v_reason_code, p_client_ip, p_user_agent
        );

        RETURN QUERY SELECT FALSE, NULL::BIGINT, NULL::VARCHAR, v_reason_code, v_message;
        RETURN;
    END IF;

    IF NOT v_user.is_active THEN
        v_reason_code := 'USER_INACTIVE';
        v_message := 'Usuario inactivo. Contacte al administrador.';

        INSERT INTO app_auth.auth_login_attempt (
            user_id, username_input, is_success, reason_code, client_ip, user_agent
        ) VALUES (
            v_user.id, COALESCE(p_username, ''), FALSE, v_reason_code, p_client_ip, p_user_agent
        );

        RETURN QUERY SELECT FALSE, v_user.id, v_user.username::VARCHAR, v_reason_code, v_message;
        RETURN;
    END IF;

    IF v_user.locked_until IS NOT NULL AND v_user.locked_until > NOW() THEN
        v_reason_code := 'ACCOUNT_LOCKED';
        v_message := 'Cuenta temporalmente bloqueada. Intente más tarde.';

        INSERT INTO app_auth.auth_login_attempt (
            user_id, username_input, is_success, reason_code, client_ip, user_agent
        ) VALUES (
            v_user.id, COALESCE(p_username, ''), FALSE, v_reason_code, p_client_ip, p_user_agent
        );

        RETURN QUERY SELECT FALSE, v_user.id, v_user.username::VARCHAR, v_reason_code, v_message;
        RETURN;
    END IF;

    v_password_ok := (
        v_user.password_hash = encode(
            digest(COALESCE(p_password, '') || COALESCE(v_user.password_salt, ''), 'sha256'),
            'hex'
        )
    );

    IF v_password_ok THEN
        UPDATE app_auth.app_user
           SET failed_attempts = 0,
               locked_until = NULL,
               last_login_at = NOW(),
               updated_at = NOW(),
               updated_by = 'sp_validate_login'
         WHERE id = v_user.id;

        v_reason_code := 'OK';
        v_message := 'Autenticación exitosa.';

        INSERT INTO app_auth.auth_login_attempt (
            user_id, username_input, is_success, reason_code, client_ip, user_agent
        ) VALUES (
            v_user.id, COALESCE(p_username, ''), TRUE, v_reason_code, p_client_ip, p_user_agent
        );

        RETURN QUERY SELECT TRUE, v_user.id, v_user.username::VARCHAR, v_reason_code, v_message;
        RETURN;
    END IF;

    UPDATE app_auth.app_user
       SET failed_attempts = failed_attempts + 1,
           locked_until = CASE
               WHEN failed_attempts + 1 >= 5 THEN NOW() + INTERVAL '15 minutes'
               ELSE locked_until
           END,
           updated_at = NOW(),
           updated_by = 'sp_validate_login'
     WHERE id = v_user.id
     RETURNING * INTO v_user;

    v_reason_code := 'BAD_PASSWORD';
    v_message := 'Usuario o contraseña inválidos.';

    INSERT INTO app_auth.auth_login_attempt (
        user_id, username_input, is_success, reason_code, client_ip, user_agent
    ) VALUES (
        v_user.id, COALESCE(p_username, ''), FALSE, v_reason_code, p_client_ip, p_user_agent
    );

    RETURN QUERY SELECT FALSE, v_user.id, v_user.username::VARCHAR, v_reason_code, v_message;
END;
$$;

COMMIT;
