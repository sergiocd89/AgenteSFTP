import streamlit as st
import os
import hashlib
import json
from core.domain import auth_service
from core.infrastructure.prompt_repository import read_agent_prompt
from core.infrastructure import auth_db
from core.logger import get_logger

try:
    import psycopg
except ImportError:  # pragma: no cover - covered indirectly when dependency is installed
    psycopg = None

try:
    import pyodbc
except ImportError:  # pragma: no cover - covered indirectly when dependency is installed
    pyodbc = None

logger = get_logger(__name__)

# --- 0. AUTENTICACIÓN ---
def _load_users_from_env() -> dict[str, str]:
    """Carga usuarios desde AUTH_USERS_JSON o AUTH_USER/AUTH_PASSWORD."""
    raw_json = os.getenv("AUTH_USERS_JSON", "").strip()
    if raw_json:
        try:
            loaded = json.loads(raw_json)
            if isinstance(loaded, dict):
                return {
                    str(user).strip(): str(password_hash).strip()
                    for user, password_hash in loaded.items()
                    if str(user).strip() and str(password_hash).strip()
                }
            logger.error("AUTH_USERS_JSON debe ser un objeto JSON user -> sha256_hash")
        except json.JSONDecodeError:
            logger.error("AUTH_USERS_JSON no tiene un formato JSON valido")

    single_user = os.getenv("AUTH_USER", "").strip()
    single_password = os.getenv("AUTH_PASSWORD", "").strip()
    if single_user and single_password:
        return {single_user: hashlib.sha256(single_password.encode()).hexdigest()}

    return {}


_USERS: dict[str, str] = _load_users_from_env()


def _get_auth_provider() -> str:
    """Retorna el proveedor de autenticación configurado: env o postgres."""
    return auth_db.get_auth_provider()


def _check_credentials_postgres(username: str, password: str) -> bool:
    """Valida credenciales contra PostgreSQL mediante función almacenada."""
    if psycopg is None:
        logger.error("psycopg no está instalado. Agrega la dependencia para usar AUTH_PROVIDER=postgres.")
        return False

    database_url = auth_db.get_database_url()
    if not database_url:
        logger.error("DATABASE_URL es obligatorio cuando AUTH_PROVIDER=postgres.")
        return False

    ok = auth_db.check_credentials_postgres(username, password, psycopg)
    if not ok:
        logger.error("No fue posible validar credenciales en PostgreSQL.")
    return ok


def _build_sqlserver_conn_str() -> str:
    """Construye string de conexión ODBC para SQL Server."""
    return auth_db.build_sqlserver_conn_str()


def _check_credentials_sqlserver(username: str, password: str) -> bool:
    """Valida credenciales contra SQL Server mediante stored procedure."""
    if pyodbc is None:
        logger.error("pyodbc no está instalado. Agrega la dependencia para usar AUTH_PROVIDER=sqlserver.")
        return False

    conn_str = _build_sqlserver_conn_str()
    if not conn_str:
        logger.error(
            "Config SQL Server incompleta. Define SQLSERVER_HOST, SQLSERVER_DATABASE, SQLSERVER_USER y SQLSERVER_PASSWORD."
        )
        return False

    ok = auth_db.check_credentials_sqlserver(username, password, pyodbc)
    if not ok:
        logger.error("No fue posible validar credenciales en SQL Server.")
    return ok

def check_credentials(username: str, password: str) -> bool:
    """Verifica credenciales con comparación segura contra timing attacks."""
    auth_provider = _get_auth_provider()
    if auth_provider in {"postgres", "postgresql", "db"}:
        return _check_credentials_postgres(username, password)
    if auth_provider in {"sqlserver", "mssql"}:
        return _check_credentials_sqlserver(username, password)

    # En modo env recargamos credenciales para reflejar cambios dinámicos en variables.
    users = _load_users_from_env() or _USERS

    if not users:
        logger.warning("No hay usuarios configurados. Define AUTH_USERS_JSON o AUTH_USER/AUTH_PASSWORD.")
        return False

    return auth_service.check_credentials(username, password, users, psycopg, pyodbc)


def change_user_password(username: str, current_password: str, new_password: str) -> tuple[bool, str]:
    """Cambia la contraseña del usuario autenticado según AUTH_PROVIDER."""
    safe_username = (username or "").strip()
    safe_current = (current_password or "").strip()
    safe_new = (new_password or "").strip()

    if not safe_username:
        return False, "Usuario inválido para cambio de contraseña."
    if not safe_current:
        return False, "Debes ingresar tu contraseña actual."
    if not safe_new:
        return False, "Debes ingresar una nueva contraseña."
    if safe_current == safe_new:
        return False, "La nueva contraseña debe ser diferente a la actual."

    users = _load_users_from_env() or _USERS
    ok, message = auth_service.change_password(safe_username, safe_current, safe_new, users, psycopg, pyodbc)

    # En modo env, persistimos el cambio al menos en memoria de proceso.
    if ok and _get_auth_provider() in {"env", ""}:
        _USERS.clear()
        _USERS.update(users)
        os.environ["AUTH_USERS_JSON"] = json.dumps(users)

    return ok, message

# --- 1. GESTIÓN DE PROMPTS ---
@st.cache_data(ttl=3600)
def load_agent_prompt(filename: str) -> str:
    """Carga en caché prompts de agente desde infraestructura."""
    return read_agent_prompt(filename)

def step_header(text: str) -> None:
    """Genera un encabezado visual consistente para los pasos del pipeline."""
    safe_text = (text or "").strip()
    if not safe_text:
        raise ValueError("El texto del encabezado no puede estar vacío.")
    st.markdown(f"### {safe_text}")
    st.divider()
