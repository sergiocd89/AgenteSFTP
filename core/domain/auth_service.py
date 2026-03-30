from core.infrastructure import auth_db


def check_credentials(
    username: str,
    password: str,
    users: dict[str, str],
    psycopg_module,
    pyodbc_module,
) -> bool:
    """Validate credentials using configured provider."""
    provider = auth_db.get_auth_provider()

    if provider in {"postgres", "postgresql", "db"}:
        return auth_db.check_credentials_postgres(username, password, psycopg_module)
    if provider in {"sqlserver", "mssql"}:
        return auth_db.check_credentials_sqlserver(username, password, pyodbc_module)

    return auth_db.check_credentials_env(users, username, password)


def change_password(
    username: str,
    current_password: str,
    new_password: str,
    users: dict[str, str],
    psycopg_module,
    pyodbc_module,
) -> tuple[bool, str]:
    """Change password for authenticated user using configured provider."""
    if not check_credentials(username, current_password, users, psycopg_module, pyodbc_module):
        return False, "La contraseña actual no es válida."

    provider = auth_db.get_auth_provider()
    if provider in {"postgres", "postgresql", "db"}:
        return auth_db.change_password_postgres(username, new_password, username, psycopg_module)
    if provider in {"sqlserver", "mssql"}:
        return auth_db.change_password_sqlserver(username, new_password, username, pyodbc_module)

    return auth_db.change_password_env(users, username, new_password)
