import os

import openai

from core.domain.contracts import make_result


class OpenAILlmGateway:
    """Implementacion de infraestructura para proveedor OpenAI."""

    def generate(
        self,
        system_role: str,
        user_content: str,
        model: str,
        temp: float,
    ) -> dict:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return make_result(False, "API Key no encontrada en el entorno.", error_code="missing_api_key")

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
            return make_result(True, "LLM response OK.", data={"content": content})
        except openai.RateLimitError as exc:
            return make_result(False, f"Limite de uso alcanzado: {exc}", error_code="rate_limit")
        except (openai.APITimeoutError, openai.APIConnectionError) as exc:
            return make_result(False, f"Error de conectividad con IA: {exc}", error_code="connection_error")
        except openai.OpenAIError as exc:
            return make_result(False, f"Error de OpenAI: {exc}", error_code="openai_error")
        except Exception as exc:
            return make_result(False, f"Error inesperado en IA: {exc}", error_code="unexpected_error")
