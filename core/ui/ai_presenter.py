import streamlit as st

from core.login import ensure_backend_token_fresh, run_backend_operation_with_retry
from core.domain.ai_service import call_llm as domain_call_llm
from core.infrastructure import backend_api_client
from core.infrastructure.llm.factory import resolve_llm_gateway
from core.logger import get_logger, log_operation


logger = get_logger(__name__)


def run_llm_text(system_role: str, user_content: str, model: str, temp: float) -> str | None:
    """Adaptador de UI para ejecutar LLM y mostrar errores amigables en Streamlit."""
    ensure_backend_token_fresh()
    token = str(st.session_state.get("backend_access_token", "") or "")
    if backend_api_client.is_backend_enabled() and token:
        ok, payload = run_backend_operation_with_retry(
            lambda current_token: backend_api_client.generate_llm(
                current_token,
                system_role,
                user_content,
                model,
                temp,
            )
        )
        if ok:
            return payload.get("content")

        error_code = payload.get("error_code")
        message = payload.get("message", "Error en llamada LLM.")
        log_operation(logger, "ui_run_llm_text", False, error_code, message)
        st.error(f"❌ Error backend LLM: {message}")
        return None

    gateway, provider = resolve_llm_gateway()
    if gateway is None:
        st.error(f"❌ Proveedor LLM no soportado: {provider}. Usa openai o vertex_gemini.")
        return None

    result = domain_call_llm(system_role, user_content, model, temp, llm_gateway=gateway)
    if result.get("success"):
        data = result.get("data") or {}
        return data.get("content")

    error_code = result.get("error_code")
    message = result.get("message", "Error en llamada LLM.")
    log_operation(logger, "ui_run_llm_text", False, error_code, message)

    if error_code == "missing_api_key":
        st.error("🔑 API Key no encontrada en el archivo .env")
    elif error_code == "missing_vertex_config":
        st.error("❌ Configuración incompleta de Vertex. Revisa proyecto, region y modelo.")
    elif error_code == "missing_vertex_dependency":
        st.error("❌ Falta dependencia de Vertex AI. Instala google-cloud-aiplatform.")
    elif error_code == "missing_gateway":
        st.error("❌ No hay proveedor de IA configurado para este entorno.")
    elif error_code == "rate_limit":
        st.error(f"❌ Límite de uso de IA alcanzado. Intenta nuevamente en unos segundos. Detalle: {message}")
    elif error_code == "connection_error":
        st.error(f"❌ No se pudo conectar con el servicio de IA. Detalle: {message}")
    elif error_code == "vertex_error":
        st.error(f"❌ Error de Vertex AI. Detalle: {message}")
    else:
        st.error(f"❌ Error en la llamada a la IA: {message}")

    return None
