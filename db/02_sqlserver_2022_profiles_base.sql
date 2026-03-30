-- 02_sqlserver_2022_profiles_base.sql
-- Objetivo: catálogo de módulos y permisos por usuario.

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'app_auth')
    EXEC('CREATE SCHEMA app_auth');
GO

IF OBJECT_ID('app_auth.profile_module', 'U') IS NULL
BEGIN
    CREATE TABLE app_auth.profile_module (
        module_key VARCHAR(80) PRIMARY KEY,
        module_label NVARCHAR(120) NOT NULL,
        app_mode VARCHAR(80) NOT NULL,
        is_active BIT NOT NULL CONSTRAINT DF_profile_module_is_active DEFAULT (1),
        created_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_profile_module_created_at DEFAULT (SYSUTCDATETIME()),
        updated_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_profile_module_updated_at DEFAULT (SYSUTCDATETIME()),
        created_by NVARCHAR(100) NULL,
        updated_by NVARCHAR(100) NULL
    );
END;
GO

IF OBJECT_ID('app_auth.user_module', 'U') IS NULL
BEGIN
    CREATE TABLE app_auth.user_module (
        user_id BIGINT NOT NULL,
        module_key VARCHAR(80) NOT NULL,
        granted_at DATETIMEOFFSET NOT NULL CONSTRAINT DF_user_module_granted_at DEFAULT (SYSUTCDATETIME()),
        granted_by NVARCHAR(100) NULL,
        CONSTRAINT PK_user_module PRIMARY KEY (user_id, module_key),
        CONSTRAINT FK_user_module_user FOREIGN KEY (user_id) REFERENCES app_auth.app_user(id) ON DELETE CASCADE,
        CONSTRAINT FK_user_module_module FOREIGN KEY (module_key) REFERENCES app_auth.profile_module(module_key)
    );
END;
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_user_module_user_id' AND object_id = OBJECT_ID('app_auth.user_module'))
    CREATE INDEX IX_user_module_user_id ON app_auth.user_module (user_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_user_module_module_key' AND object_id = OBJECT_ID('app_auth.user_module'))
    CREATE INDEX IX_user_module_module_key ON app_auth.user_module (module_key);
GO

MERGE app_auth.profile_module AS t
USING (
    SELECT 'SFTP' AS module_key, N'🔐 FTP ➔ SFTP' AS module_label, 'SFTP_Module' AS app_mode
    UNION ALL SELECT 'COBOL', N'🐍 COBOL ➔ Python', 'COBOL_Module'
    UNION ALL SELECT 'DTSX', N'📦 COBOL ➔ DTSX', 'DTSX_Module'
    UNION ALL SELECT 'RequirementWorkflow', N'🧩 Requirement Workflow', 'Requirement_Workflow_Module'
    UNION ALL SELECT 'Documentation', N'📝 Documentación', 'Documentation_Module'
) AS s
ON t.module_key = s.module_key
WHEN MATCHED THEN
    UPDATE SET module_label = s.module_label,
               app_mode = s.app_mode,
               is_active = 1,
               updated_by = N'bootstrap',
               updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (module_key, module_label, app_mode, is_active, created_by, updated_by)
    VALUES (s.module_key, s.module_label, s.app_mode, 1, N'bootstrap', N'bootstrap');
GO

CREATE OR ALTER PROCEDURE app_auth.sp_grant_module_to_user
    @username NVARCHAR(150),
    @module_key VARCHAR(80),
    @actor NVARCHAR(100) = N'system'
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @user_id BIGINT;
    SELECT @user_id = id
      FROM app_auth.app_user
     WHERE username = LTRIM(RTRIM(ISNULL(@username, N'')))
       AND is_active = 1;

    IF @user_id IS NULL
        THROW 52000, 'usuario no existe o está inactivo', 1;

    IF NOT EXISTS (SELECT 1 FROM app_auth.profile_module WHERE module_key = LTRIM(RTRIM(ISNULL(@module_key, ''))) AND is_active = 1)
        THROW 52001, 'módulo no existe o está inactivo', 1;

    INSERT INTO app_auth.user_module (user_id, module_key, granted_by)
    SELECT @user_id, LTRIM(RTRIM(@module_key)), @actor
    WHERE NOT EXISTS (
        SELECT 1 FROM app_auth.user_module WHERE user_id = @user_id AND module_key = LTRIM(RTRIM(@module_key))
    );
END;
GO

CREATE OR ALTER PROCEDURE app_auth.sp_revoke_module_from_user
    @username NVARCHAR(150),
    @module_key VARCHAR(80)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @user_id BIGINT;
    SELECT @user_id = id FROM app_auth.app_user WHERE username = LTRIM(RTRIM(ISNULL(@username, N'')));

    IF @user_id IS NULL
        THROW 52002, 'usuario no existe', 1;

    DELETE FROM app_auth.user_module WHERE user_id = @user_id AND module_key = LTRIM(RTRIM(ISNULL(@module_key, '')));
END;
GO

CREATE OR ALTER FUNCTION app_auth.fn_is_admin (@username NVARCHAR(150))
RETURNS BIT
AS
BEGIN
    DECLARE @is_admin BIT = 0;
    SELECT @is_admin = is_admin
      FROM app_auth.app_user
     WHERE username = LTRIM(RTRIM(ISNULL(@username, N'')))
       AND is_active = 1;

    RETURN ISNULL(@is_admin, 0);
END;
GO

CREATE OR ALTER PROCEDURE app_auth.sp_get_user_modules
    @username NVARCHAR(150)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT um.module_key
      FROM app_auth.app_user u
      JOIN app_auth.user_module um ON um.user_id = u.id
      JOIN app_auth.profile_module pm ON pm.module_key = um.module_key
     WHERE u.username = LTRIM(RTRIM(ISNULL(@username, N'')))
       AND u.is_active = 1
       AND pm.is_active = 1
     ORDER BY um.module_key;
END;
GO
