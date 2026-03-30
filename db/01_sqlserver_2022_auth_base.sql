-- 01_sqlserver_2022_auth_base.sql
-- Objetivo: crear base de autenticación desde cero para SQL Server 2022.

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'app_auth')
    EXEC('CREATE SCHEMA app_auth');
GO

IF OBJECT_ID('app_auth.app_user', 'U') IS NULL
BEGIN
    CREATE TABLE app_auth.app_user (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(150) NOT NULL,
        password_salt VARCHAR(32) NOT NULL,
        password_hash CHAR(64) NOT NULL,
        full_name NVARCHAR(200) NULL,
        is_admin BIT NOT NULL CONSTRAINT DF_app_user_is_admin DEFAULT (0),
        is_active BIT NOT NULL CONSTRAINT DF_app_user_is_active DEFAULT (1),
        failed_attempts INT NOT NULL CONSTRAINT DF_app_user_failed_attempts DEFAULT (0),
        locked_until DATETIMEOFFSET NULL,
        last_login_at DATETIMEOFFSET NULL,
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_app_user_created_at DEFAULT (SYSUTCDATETIME()),
        updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_app_user_updated_at DEFAULT (SYSUTCDATETIME()),
        created_by NVARCHAR(100) NULL,
        updated_by NVARCHAR(100) NULL,
        CONSTRAINT UQ_app_user_username UNIQUE (username)
    );
END;
GO

IF OBJECT_ID('app_auth.auth_login_attempt', 'U') IS NULL
BEGIN
    CREATE TABLE app_auth.auth_login_attempt (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        user_id BIGINT NULL,
        username_input NVARCHAR(150) NOT NULL,
        is_success BIT NOT NULL,
        reason_code VARCHAR(40) NOT NULL,
        client_ip VARCHAR(45) NULL,
        user_agent NVARCHAR(500) NULL,
        attempted_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_auth_login_attempt_attempted_at DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_auth_login_attempt_user FOREIGN KEY (user_id) REFERENCES app_auth.app_user(id)
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_auth_login_attempt_attempted_at' AND object_id = OBJECT_ID('app_auth.auth_login_attempt'))
    CREATE INDEX IX_auth_login_attempt_attempted_at ON app_auth.auth_login_attempt (attempted_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_auth_login_attempt_username_input' AND object_id = OBJECT_ID('app_auth.auth_login_attempt'))
    CREATE INDEX IX_auth_login_attempt_username_input ON app_auth.auth_login_attempt (username_input);
GO

CREATE OR ALTER PROCEDURE app_auth.sp_create_user
    @username NVARCHAR(150),
    @plain_password NVARCHAR(400),
    @full_name NVARCHAR(200) = NULL,
    @is_admin BIT = 0,
    @is_active BIT = 1,
    @actor NVARCHAR(100) = N'system'
AS
BEGIN
    SET NOCOUNT ON;

    IF NULLIF(LTRIM(RTRIM(@username)), N'') IS NULL
        THROW 51000, 'username es requerido', 1;

    IF NULLIF(LTRIM(RTRIM(@plain_password)), N'') IS NULL
        THROW 51001, 'password es requerido', 1;

    DECLARE @salt VARCHAR(32) = CONVERT(VARCHAR(32), CRYPT_GEN_RANDOM(16), 2);
    DECLARE @hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', CONCAT(@plain_password, @salt)), 2);

    MERGE app_auth.app_user AS target
    USING (SELECT LTRIM(RTRIM(@username)) AS username) AS source
    ON target.username = source.username
    WHEN MATCHED THEN
        UPDATE SET
            password_salt = @salt,
            password_hash = @hash,
            full_name = NULLIF(LTRIM(RTRIM(@full_name)), N''),
            is_admin = @is_admin,
            is_active = @is_active,
            updated_by = @actor,
            updated_at = SYSUTCDATETIME()
    WHEN NOT MATCHED THEN
        INSERT (
            username, password_salt, password_hash, full_name,
            is_admin, is_active, created_by, updated_by
        )
        VALUES (
            LTRIM(RTRIM(@username)), @salt, @hash, NULLIF(LTRIM(RTRIM(@full_name)), N''),
            @is_admin, @is_active, @actor, @actor
        );
END;
GO

CREATE OR ALTER PROCEDURE app_auth.sp_change_password
    @username NVARCHAR(150),
    @new_plain_password NVARCHAR(400),
    @actor NVARCHAR(100) = N'system'
AS
BEGIN
    SET NOCOUNT ON;

    IF NULLIF(LTRIM(RTRIM(@username)), N'') IS NULL
        THROW 51002, 'username es requerido', 1;

    IF NULLIF(LTRIM(RTRIM(@new_plain_password)), N'') IS NULL
        THROW 51003, 'new password es requerido', 1;

    DECLARE @salt VARCHAR(32) = CONVERT(VARCHAR(32), CRYPT_GEN_RANDOM(16), 2);
    DECLARE @hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', CONCAT(@new_plain_password, @salt)), 2);

    UPDATE app_auth.app_user
       SET password_salt = @salt,
           password_hash = @hash,
           failed_attempts = 0,
           locked_until = NULL,
           updated_by = @actor,
           updated_at = SYSUTCDATETIME()
     WHERE username = LTRIM(RTRIM(@username));

    IF @@ROWCOUNT = 0
        THROW 51004, 'usuario no existe', 1;
END;
GO

CREATE OR ALTER PROCEDURE app_auth.sp_validate_login
    @username NVARCHAR(150),
    @password NVARCHAR(400),
    @client_ip VARCHAR(45) = NULL,
    @user_agent NVARCHAR(500) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @user_id BIGINT;
    DECLARE @db_username NVARCHAR(150);
    DECLARE @db_salt VARCHAR(32);
    DECLARE @db_hash CHAR(64);
    DECLARE @is_active BIT;
    DECLARE @failed_attempts INT;
    DECLARE @locked_until DATETIMEOFFSET;

    SELECT
        @user_id = id,
        @db_username = username,
        @db_salt = password_salt,
        @db_hash = password_hash,
        @is_active = is_active,
        @failed_attempts = failed_attempts,
        @locked_until = locked_until
    FROM app_auth.app_user
    WHERE username = LTRIM(RTRIM(ISNULL(@username, N'')));

    IF @user_id IS NULL
    BEGIN
        INSERT INTO app_auth.auth_login_attempt (user_id, username_input, is_success, reason_code, client_ip, user_agent)
        VALUES (NULL, ISNULL(@username, N''), 0, 'USER_NOT_FOUND', @client_ip, @user_agent);

        SELECT CAST(0 AS BIT) AS auth_ok,
               CAST(NULL AS BIGINT) AS user_id,
               CAST(NULL AS NVARCHAR(150)) AS username,
               CAST('USER_NOT_FOUND' AS VARCHAR(40)) AS reason_code,
               CAST('Usuario o contraseña inválidos.' AS NVARCHAR(200)) AS message;
        RETURN;
    END;

    IF @is_active = 0
    BEGIN
        INSERT INTO app_auth.auth_login_attempt (user_id, username_input, is_success, reason_code, client_ip, user_agent)
        VALUES (@user_id, ISNULL(@username, N''), 0, 'USER_INACTIVE', @client_ip, @user_agent);

        SELECT CAST(0 AS BIT) AS auth_ok,
               @user_id AS user_id,
               @db_username AS username,
               CAST('USER_INACTIVE' AS VARCHAR(40)) AS reason_code,
               CAST('Usuario inactivo. Contacte al administrador.' AS NVARCHAR(200)) AS message;
        RETURN;
    END;

    IF @locked_until IS NOT NULL AND @locked_until > SYSUTCDATETIME()
    BEGIN
        INSERT INTO app_auth.auth_login_attempt (user_id, username_input, is_success, reason_code, client_ip, user_agent)
        VALUES (@user_id, ISNULL(@username, N''), 0, 'ACCOUNT_LOCKED', @client_ip, @user_agent);

        SELECT CAST(0 AS BIT) AS auth_ok,
               @user_id AS user_id,
               @db_username AS username,
               CAST('ACCOUNT_LOCKED' AS VARCHAR(40)) AS reason_code,
               CAST('Cuenta temporalmente bloqueada. Intente más tarde.' AS NVARCHAR(200)) AS message;
        RETURN;
    END;

    DECLARE @input_hash CHAR(64) = CONVERT(CHAR(64), HASHBYTES('SHA2_256', CONCAT(ISNULL(@password, N''), ISNULL(@db_salt, ''))), 2);

    IF @input_hash = @db_hash
    BEGIN
        UPDATE app_auth.app_user
           SET failed_attempts = 0,
               locked_until = NULL,
               last_login_at = SYSUTCDATETIME(),
               updated_at = SYSUTCDATETIME(),
               updated_by = 'sp_validate_login'
         WHERE id = @user_id;

        INSERT INTO app_auth.auth_login_attempt (user_id, username_input, is_success, reason_code, client_ip, user_agent)
        VALUES (@user_id, ISNULL(@username, N''), 1, 'OK', @client_ip, @user_agent);

        SELECT CAST(1 AS BIT) AS auth_ok,
               @user_id AS user_id,
               @db_username AS username,
               CAST('OK' AS VARCHAR(40)) AS reason_code,
               CAST('Autenticación exitosa.' AS NVARCHAR(200)) AS message;
        RETURN;
    END;

    UPDATE app_auth.app_user
       SET failed_attempts = failed_attempts + 1,
           locked_until = CASE WHEN failed_attempts + 1 >= 5 THEN DATEADD(MINUTE, 15, SYSUTCDATETIME()) ELSE locked_until END,
           updated_at = SYSUTCDATETIME(),
           updated_by = 'sp_validate_login'
     WHERE id = @user_id;

    INSERT INTO app_auth.auth_login_attempt (user_id, username_input, is_success, reason_code, client_ip, user_agent)
    VALUES (@user_id, ISNULL(@username, N''), 0, 'BAD_PASSWORD', @client_ip, @user_agent);

    SELECT CAST(0 AS BIT) AS auth_ok,
           @user_id AS user_id,
           @db_username AS username,
           CAST('BAD_PASSWORD' AS VARCHAR(40)) AS reason_code,
           CAST('Usuario o contraseña inválidos.' AS NVARCHAR(200)) AS message;
END;
GO
