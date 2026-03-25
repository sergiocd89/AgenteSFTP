import streamlit as st
import os
import hashlib
import hmac
import json
from dotenv import load_dotenv
from core.infrastructure.prompt_repository import read_agent_prompt
from core.logger import get_logger

# Cargamos variables de entorno una sola vez
load_dotenv()
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

def check_credentials(username: str, password: str) -> bool:
    """Verifica credenciales con comparación segura contra timing attacks."""
    if not _USERS:
        logger.warning("No hay usuarios configurados. Define AUTH_USERS_JSON o AUTH_USER/AUTH_PASSWORD.")
        return False

    stored_hash = _USERS.get(username)
    if not stored_hash:
        return False
    input_hash = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(stored_hash, input_hash)

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
