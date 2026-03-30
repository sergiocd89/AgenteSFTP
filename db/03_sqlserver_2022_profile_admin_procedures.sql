-- 03_sqlserver_2022_profile_admin_procedures.sql
-- Objetivo: SPs para creación/edición de usuarios y administración de perfiles.

CREATE OR ALTER PROCEDURE app_auth.sp_create_user_profile
    @username NVARCHAR(150),
    @plain_password NVARCHAR(400),
    @full_name NVARCHAR(200) = NULL,
    @is_admin BIT = 0,
    @is_active BIT = 1,
    @modules_csv NVARCHAR(MAX) = NULL,
    @actor NVARCHAR(100) = N'profile-admin'
AS
BEGIN
    SET NOCOUNT ON;

    IF NULLIF(LTRIM(RTRIM(@username)), N'') IS NULL
        THROW 53000, 'username es requerido', 1;

    IF NULLIF(LTRIM(RTRIM(@plain_password)), N'') IS NULL
        THROW 53001, 'password es requerido', 1;

    EXEC app_auth.sp_create_user
        @username = @username,
        @plain_password = @plain_password,
        @full_name = @full_name,
        @is_admin = @is_admin,
        @is_active = @is_active,
        @actor = @actor;

    DECLARE @user_id BIGINT;
    SELECT @user_id = id FROM app_auth.app_user WHERE username = LTRIM(RTRIM(@username));

    IF @user_id IS NULL
        THROW 53002, 'no se pudo recuperar user_id', 1;

    DELETE FROM app_auth.user_module WHERE user_id = @user_id;

    IF NULLIF(LTRIM(RTRIM(ISNULL(@modules_csv, N''))), N'') IS NOT NULL
    BEGIN
        ;WITH mods AS (
            SELECT DISTINCT LTRIM(RTRIM(value)) AS module_key
            FROM STRING_SPLIT(@modules_csv, ',')
            WHERE LTRIM(RTRIM(value)) <> ''
        )
        INSERT INTO app_auth.user_module (user_id, module_key, granted_by)
        SELECT @user_id, m.module_key, @actor
        FROM mods m
        JOIN app_auth.profile_module pm ON pm.module_key = m.module_key AND pm.is_active = 1
        WHERE NOT EXISTS (
            SELECT 1 FROM app_auth.user_module um WHERE um.user_id = @user_id AND um.module_key = m.module_key
        );
    END;
END;
GO

CREATE OR ALTER PROCEDURE app_auth.sp_update_user_profile
    @username NVARCHAR(150),
    @full_name NVARCHAR(200) = NULL,
    @is_admin BIT = NULL,
    @is_active BIT = NULL,
    @modules_csv NVARCHAR(MAX) = NULL,
    @actor NVARCHAR(100) = N'profile-admin'
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @user_id BIGINT;
    SELECT @user_id = id FROM app_auth.app_user WHERE username = LTRIM(RTRIM(ISNULL(@username, N'')));

    IF @user_id IS NULL
        THROW 53003, 'usuario no existe', 1;

    UPDATE app_auth.app_user
       SET full_name = COALESCE(NULLIF(LTRIM(RTRIM(@full_name)), N''), full_name),
           is_admin = COALESCE(@is_admin, is_admin),
           is_active = COALESCE(@is_active, is_active),
           updated_by = @actor,
           updated_at = SYSUTCDATETIME()
     WHERE id = @user_id;

    IF @modules_csv IS NOT NULL
    BEGIN
        DELETE FROM app_auth.user_module WHERE user_id = @user_id;

        ;WITH mods AS (
            SELECT DISTINCT LTRIM(RTRIM(value)) AS module_key
            FROM STRING_SPLIT(@modules_csv, ',')
            WHERE LTRIM(RTRIM(value)) <> ''
        )
        INSERT INTO app_auth.user_module (user_id, module_key, granted_by)
        SELECT @user_id, m.module_key, @actor
        FROM mods m
        JOIN app_auth.profile_module pm ON pm.module_key = m.module_key AND pm.is_active = 1;
    END;
END;
GO

CREATE OR ALTER PROCEDURE app_auth.sp_admin_reset_password
    @username NVARCHAR(150),
    @new_plain_password NVARCHAR(400),
    @actor NVARCHAR(100) = N'profile-admin'
AS
BEGIN
    SET NOCOUNT ON;
    EXEC app_auth.sp_change_password @username, @new_plain_password, @actor;
END;
GO

CREATE OR ALTER PROCEDURE app_auth.sp_deactivate_user
    @username NVARCHAR(150),
    @actor NVARCHAR(100) = N'profile-admin'
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE app_auth.app_user
       SET is_active = 0,
           updated_by = @actor,
           updated_at = SYSUTCDATETIME()
     WHERE username = LTRIM(RTRIM(ISNULL(@username, N'')));

    IF @@ROWCOUNT = 0
        THROW 53004, 'usuario no existe', 1;
END;
GO
