from typing import Protocol


class LlmGateway(Protocol):
    """Contrato de dominio para proveedores LLM."""

    def generate(
        self,
        system_role: str,
        user_content: str,
        model: str,
        temp: float,
    ) -> dict:
        ...
