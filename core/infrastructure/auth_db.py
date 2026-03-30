import os
import hashlib
import hmac
from typing import Any


def get_auth_provider() -> str:
    """Return configured provider for auth/profile persistence."""
    return os.getenv("AUTH_PROVIDER", "env").strip().lower()


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def build_sqlserver_conn_str() -> str:
    """Build ODBC connection string for SQL Server."""
    driver = os.getenv("SQLSERVER_DRIVER", "ODBC Driver 18 for SQL Server").strip()
    host = os.getenv("SQLSERVER_HOST", "").strip()
    port = os.getenv("SQLSERVER_PORT", "1433").strip()
    database = os.getenv("SQLSERVER_DATABASE", "").strip()
    user = os.getenv("SQLSERVER_USER", "").strip()
    password = os.getenv("SQLSERVER_PASSWORD", "").strip()
    trust = os.getenv("SQLSERVER_TRUST_SERVER_CERTIFICATE", "yes").strip().lower()

    if not all([host, database, user, password]):
        return ""

    trust_value = "yes" if trust in {"1", "true", "yes", "y"} else "no"
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=yes;"
        f"TrustServerCertificate={trust_value};"
    )


def check_credentials_env(users: dict[str, str], username: str, password: str) -> bool:
    if not users:
        return False
    stored_hash = users.get(username)
    if not stored_hash:
        return False
    input_hash = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(stored_hash, input_hash)


def check_credentials_postgres(
    username: str,
    password: str,
    psycopg_module: Any,
) -> bool:
    """Validate credentials against PostgreSQL stored function."""
    if psycopg_module is None:
        return False

    database_url = get_database_url()
    if not database_url:
        return False

    try:
        with psycopg_module.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT auth_ok FROM app_auth.sp_validate_login(%s, %s, %s, %s);",
                    (username, password, None, "streamlit"),
                )
                row = cur.fetchone()
                return bool(row and row[0])
    except Exception:
        return False


def check_credentials_sqlserver(
    username: str,
    password: str,
    pyodbc_module: Any,
) -> bool:
    """Validate credentials against SQL Server stored procedure."""
    if pyodbc_module is None:
        return False

    conn_str = build_sqlserver_conn_str()
    if not conn_str:
        return False

    try:
        with pyodbc_module.connect(conn_str, timeout=5) as conn:
            cur = conn.cursor()
            cur.execute(
                "EXEC app_auth.sp_validate_login @username=?, @password=?, @client_ip=?, @user_agent=?;",
                username,
                password,
                None,
                "streamlit",
            )
            row = cur.fetchone()
            return bool(row and row[0])
    except Exception:
        return False
