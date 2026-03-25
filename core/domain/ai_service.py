from core.domain.contracts import make_result
from core.domain.ports.llm_gateway import LlmGateway
from core.logger import get_logger, log_operation


logger = get_logger(__name__)


def call_llm(
    system_role: str,
    user_content: str,
    model: str,
    temp: float,
    llm_gateway: LlmGateway | None = None,
) -> dict:
    """Ejecuta la llamada LLM en dominio usando un puerto de infraestructura."""
    if llm_gateway is None:
        result = make_result(False, "No hay gateway LLM configurado.", error_code="missing_gateway")
        log_operation(logger, "llm_call", False, result["error_code"], result["message"])
        return result

    try:
        result = llm_gateway.generate(
            system_role=system_role,
            user_content=user_content,
            model=model,
            temp=temp,
        )

        if result.get("success"):
            log_operation(logger, "llm_call", True)
        else:
            log_operation(logger, "llm_call", False, result.get("error_code"), result.get("message"))
        return result
    except Exception as exc:
        result = make_result(False, f"Error inesperado en IA: {exc}", error_code="unexpected_error")

    log_operation(logger, "llm_call", False, result["error_code"], result["message"])
    return result
