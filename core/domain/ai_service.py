import os

import openai

from core.domain.contracts import make_result
from core.logger import get_logger, log_operation


logger = get_logger(__name__)


def call_llm(
    system_role: str,
    user_content: str,
    model: str,
    temp: float,
) -> dict:
    """Ejecuta llamada LLM en capa dominio sin dependencia de Streamlit."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        result = make_result(False, "API Key no encontrada en el entorno.", error_code="missing_api_key")
        log_operation(logger, "llm_call", False, result["error_code"], result["message"])
        return result

    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            temperature=temp,
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": user_content},
            ],
        )
        content = response.choices[0].message.content
        result = make_result(True, "LLM response OK.", data={"content": content})
        log_operation(logger, "llm_call", True)
        return result
    except openai.RateLimitError as exc:
        result = make_result(False, f"Límite de uso alcanzado: {exc}", error_code="rate_limit")
    except (openai.APITimeoutError, openai.APIConnectionError) as exc:
        result = make_result(False, f"Error de conectividad con IA: {exc}", error_code="connection_error")
    except openai.OpenAIError as exc:
        result = make_result(False, f"Error de OpenAI: {exc}", error_code="openai_error")
    except Exception as exc:
        result = make_result(False, f"Error inesperado en IA: {exc}", error_code="unexpected_error")

    log_operation(logger, "llm_call", False, result["error_code"], result["message"])
    return result
