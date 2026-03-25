import os

from core.domain.ports.llm_gateway import LlmGateway
from core.infrastructure.llm.openai_gateway import OpenAILlmGateway
from core.infrastructure.llm.vertex_gateway import VertexLlmGateway


def resolve_llm_gateway(provider: str | None = None) -> tuple[LlmGateway | None, str]:
    """Resuelve proveedor configurado y retorna su gateway."""
    selected = (provider or os.getenv("LLM_PROVIDER", "openai")).strip().lower()

    if selected in {"vertex_gemini", "vertex", "vertexai", "gemini"}:
        return VertexLlmGateway(), selected

    if selected == "openai":
        return OpenAILlmGateway(), selected

    return None, selected
