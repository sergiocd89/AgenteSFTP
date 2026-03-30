from typing import Any


def load_profiles_and_admins_from_postgres(database_url: str, psycopg_module: Any) -> tuple[dict[str, list[str]], set[str]] | None:
    if psycopg_module is None or not database_url:
        return None

    profiles: dict[str, list[str]] = {}
    admins: set[str] = set()

    try:
        with psycopg_module.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        u.username,
                        COALESCE(pm.module_key, '') AS module_key,
                        u.is_admin
                    FROM app_auth.app_user u
                    LEFT JOIN app_auth.user_module um ON um.user_id = u.id
                    LEFT JOIN app_auth.profile_module pm
                        ON pm.module_key = um.module_key
                       AND pm.is_active = TRUE
                    ORDER BY u.username, pm.module_key;
                    """
                )

                for username, module_key, is_admin in cur.fetchall():
                    safe_username = (username or "").strip()
                    if not safe_username:
                        continue
                    profiles.setdefault(safe_username, [])
                    if module_key:
                        profiles[safe_username].append(module_key)
                    if is_admin:
                        admins.add(safe_username)
    except Exception:
        return None

    if not profiles:
        return None
    if not admins:
        admins = {next(iter(profiles.keys()))}

    return profiles, admins


def load_user_profile_meta_from_postgres(database_url: str, psycopg_module: Any) -> dict[str, dict[str, object]] | None:
    if psycopg_module is None or not database_url:
        return None

    try:
        with psycopg_module.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.username, COALESCE(u.full_name, ''), u.is_admin, u.is_active
                    FROM app_auth.app_user u
                    ORDER BY u.username;
                    """
                )
                return {
                    (username or "").strip(): {
                        "full_name": (full_name or "").strip() or (username or "").strip(),
                        "is_admin": bool(is_admin),
                        "is_active": bool(is_active),
                    }
                    for username, full_name, is_admin, is_active in cur.fetchall()
                    if (username or "").strip()
                }
    except Exception:
        return None


def load_profiles_and_admins_from_sqlserver(conn_str: str, pyodbc_module: Any) -> tuple[dict[str, list[str]], set[str]] | None:
    if pyodbc_module is None or not conn_str:
        return None

    profiles: dict[str, list[str]] = {}
    admins: set[str] = set()

    try:
        with pyodbc_module.connect(conn_str, timeout=5) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    u.username,
                    ISNULL(pm.module_key, '') AS module_key,
                    u.is_admin
                FROM app_auth.app_user u
                LEFT JOIN app_auth.user_module um ON um.user_id = u.id
                LEFT JOIN app_auth.profile_module pm
                    ON pm.module_key = um.module_key
                   AND pm.is_active = 1
                ORDER BY u.username, pm.module_key;
                """
            )
            for username, module_key, is_admin in cur.fetchall():
                safe_username = (username or "").strip()
                if not safe_username:
                    continue
                profiles.setdefault(safe_username, [])
                if module_key:
                    profiles[safe_username].append(module_key)
                if is_admin:
                    admins.add(safe_username)
    except Exception:
        return None

    if not profiles:
        return None
    if not admins:
        admins = {next(iter(profiles.keys()))}

    return profiles, admins


def load_user_profile_meta_from_sqlserver(conn_str: str, pyodbc_module: Any) -> dict[str, dict[str, object]] | None:
    if pyodbc_module is None or not conn_str:
        return None

    try:
        with pyodbc_module.connect(conn_str, timeout=5) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT username, ISNULL(full_name, ''), is_admin, is_active
                FROM app_auth.app_user
                ORDER BY username;
                """
            )
            return {
                (username or "").strip(): {
                    "full_name": (full_name or "").strip() or (username or "").strip(),
                    "is_admin": bool(is_admin),
                    "is_active": bool(is_active),
                }
                for username, full_name, is_admin, is_active in cur.fetchall()
                if (username or "").strip()
            }
    except Exception:
        return None


def save_user_modules_postgres(
    database_url: str,
    psycopg_module: Any,
    username: str,
    module_keys: list[str],
    valid_modules: set[str],
    actor: str,
) -> bool:
    if psycopg_module is None or not database_url:
        return False

    valid_module_keys = [key for key in module_keys if key in valid_modules]

    try:
        with psycopg_module.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM app_auth.app_user WHERE username = %s;", (username,))
                row = cur.fetchone()
                if not row:
                    return False

                user_id = row[0]
                cur.execute("DELETE FROM app_auth.user_module WHERE user_id = %s;", (user_id,))

                for module_key in valid_module_keys:
                    cur.execute(
                        """
                        INSERT INTO app_auth.user_module (user_id, module_key, granted_by)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, module_key)
                        DO NOTHING;
                        """,
                        (user_id, module_key, actor),
                    )
            conn.commit()
    except Exception:
        return False

    return True


def update_user_profile_postgres(
    database_url: str,
    psycopg_module: Any,
    username: str,
    full_name: str,
    is_admin_user: bool,
    is_active_user: bool,
    module_keys: list[str],
    valid_modules: set[str],
    actor: str,
) -> bool:
    if psycopg_module is None or not database_url:
        return False

    valid_module_keys = [key for key in module_keys if key in valid_modules]

    try:
        with psycopg_module.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CALL app_auth.sp_update_user_profile(
                        %s, %s, %s, %s, %s, %s
                    );
                    """,
                    (
                        username,
                        (full_name or "").strip() or None,
                        bool(is_admin_user),
                        bool(is_active_user),
                        valid_module_keys,
                        actor,
                    ),
                )
            conn.commit()
    except Exception:
        return False

    return True


def update_user_profile_sqlserver(
    conn_str: str,
    pyodbc_module: Any,
    username: str,
    full_name: str,
    is_admin_user: bool,
    is_active_user: bool,
    module_keys: list[str],
    valid_modules: set[str],
    actor: str,
) -> bool:
    if pyodbc_module is None or not conn_str:
        return False

    valid_module_keys = [key for key in module_keys if key in valid_modules]
    modules_csv = ",".join(valid_module_keys)

    try:
        with pyodbc_module.connect(conn_str, timeout=5) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                EXEC app_auth.sp_update_user_profile
                    @username=?,
                    @full_name=?,
                    @is_admin=?,
                    @is_active=?,
                    @modules_csv=?,
                    @actor=?;
                """,
                username,
                (full_name or "").strip() or None,
                bool(is_admin_user),
                bool(is_active_user),
                modules_csv,
                actor,
            )
            conn.commit()
    except Exception:
        return False

    return True


def admin_reset_password_postgres(
    database_url: str,
    psycopg_module: Any,
    username: str,
    new_plain_password: str,
    actor: str,
) -> tuple[bool, str]:
    if psycopg_module is None:
        return False, "psycopg no está disponible para resetear contraseñas en PostgreSQL."
    if not database_url:
        return False, "DATABASE_URL es obligatorio para resetear contraseñas en PostgreSQL."

    safe_password = (new_plain_password or "").strip()
    if not safe_password:
        return False, "Debes ingresar una nueva contraseña."

    try:
        with psycopg_module.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CALL app_auth.sp_admin_reset_password(%s, %s, %s);
                    """,
                    (username, safe_password, actor),
                )
            conn.commit()
    except Exception as exc:
        return False, f"No fue posible resetear contraseña para {username}: {exc}"

    return True, f"Contraseña reseteada correctamente para {username}."


def admin_reset_password_sqlserver(
    conn_str: str,
    pyodbc_module: Any,
    username: str,
    new_plain_password: str,
    actor: str,
) -> tuple[bool, str]:
    if pyodbc_module is None:
        return False, "pyodbc no está disponible para resetear contraseñas en SQL Server."
    if not conn_str:
        return False, "Config SQL Server incompleta para resetear contraseñas."

    safe_password = (new_plain_password or "").strip()
    if not safe_password:
        return False, "Debes ingresar una nueva contraseña."

    try:
        with pyodbc_module.connect(conn_str, timeout=5) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                EXEC app_auth.sp_admin_reset_password @username=?, @new_plain_password=?, @actor=?;
                """,
                username,
                safe_password,
                actor,
            )
            conn.commit()
    except Exception as exc:
        return False, f"No fue posible resetear contraseña para {username}: {exc}"

    return True, f"Contraseña reseteada correctamente para {username}."


def create_user_profile_postgres(
    database_url: str,
    psycopg_module: Any,
    username: str,
    plain_password: str,
    full_name: str,
    is_admin_user: bool,
    is_active_user: bool,
    module_keys: list[str],
    valid_modules: set[str],
    actor: str,
) -> tuple[bool, str]:
    if psycopg_module is None:
        return False, "psycopg no está disponible para crear usuarios en PostgreSQL."
    if not database_url:
        return False, "DATABASE_URL es obligatorio para crear usuarios en PostgreSQL."

    valid_module_keys = [key for key in module_keys if key in valid_modules]

    try:
        with psycopg_module.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CALL app_auth.sp_create_user_profile(
                        %s, %s, %s, %s, %s, %s, %s
                    );
                    """,
                    (
                        username,
                        plain_password,
                        (full_name or "").strip() or None,
                        bool(is_admin_user),
                        bool(is_active_user),
                        valid_module_keys,
                        actor,
                    ),
                )
            conn.commit()
    except Exception as exc:
        return False, f"No fue posible crear el usuario en base de datos: {exc}"

    return True, f"Usuario {username} creado correctamente en base de datos."


def create_user_profile_sqlserver(
    conn_str: str,
    pyodbc_module: Any,
    username: str,
    plain_password: str,
    full_name: str,
    is_admin_user: bool,
    is_active_user: bool,
    module_keys: list[str],
    valid_modules: set[str],
    actor: str,
) -> tuple[bool, str]:
    if pyodbc_module is None:
        return False, "pyodbc no está disponible para crear usuarios en SQL Server."
    if not conn_str:
        return False, "Config SQL Server incompleta para crear usuarios."

    valid_module_keys = [key for key in module_keys if key in valid_modules]

    try:
        with pyodbc_module.connect(conn_str, timeout=5) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                EXEC app_auth.sp_create_user_profile
                    @username=?,
                    @plain_password=?,
                    @full_name=?,
                    @is_admin=?,
                    @is_active=?,
                    @modules_csv=?,
                    @actor=?;
                """,
                username,
                plain_password,
                (full_name or "").strip() or None,
                bool(is_admin_user),
                bool(is_active_user),
                ",".join(valid_module_keys),
                actor,
            )
            conn.commit()
    except Exception as exc:
        return False, f"No fue posible crear el usuario en SQL Server: {exc}"

    return True, f"Usuario {username} creado correctamente en SQL Server."
