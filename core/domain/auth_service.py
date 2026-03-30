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
