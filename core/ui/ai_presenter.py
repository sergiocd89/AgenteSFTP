import streamlit as st

from core.domain.ai_service import call_llm as domain_call_llm
from core.logger import get_logger, log_operation


logger = get_logger(__name__)


def run_llm_text(system_role: str, user_content: str, model: str, temp: float) -> str | None:
    """Adaptador de UI para ejecutar LLM y mostrar errores amigables en Streamlit."""
    result = domain_call_llm(system_role, user_content, model, temp)
    if result.get("success"):
        data = result.get("data") or {}
        return data.get("content")

    error_code = result.get("error_code")
    message = result.get("message", "Error en llamada LLM.")
    log_operation(logger, "ui_run_llm_text", False, error_code, message)

    if error_code == "missing_api_key":
        st.error("🔑 API Key no encontrada en el archivo .env")
    elif error_code == "rate_limit":
        st.error(f"❌ Límite de uso de IA alcanzado. Intenta nuevamente en unos segundos. Detalle: {message}")
    elif error_code == "connection_error":
        st.error(f"❌ No se pudo conectar con el servicio de IA. Detalle: {message}")
    else:
        st.error(f"❌ Error en la llamada a la IA: {message}")

    return None
