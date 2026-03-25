import importlib
import os

from core.domain.contracts import make_result


class VertexLlmGateway:
    """Implementacion de infraestructura para Vertex AI Gemini."""

    def generate(
        self,
        system_role: str,
        user_content: str,
        model: str,
        temp: float,
    ) -> dict:
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "").strip()
        fallback_model = os.getenv("VERTEX_GEMINI_MODEL", "").strip() or os.getenv("GEMINI_MODEL", "").strip()
        final_model = (model or "").strip() or fallback_model

        if not project or not location or not final_model:
            return make_result(
                False,
                "Falta configuracion de Vertex (GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION o modelo).",
                error_code="missing_vertex_config",
            )

        try:
            vertexai = importlib.import_module("vertexai")
            generative_models = importlib.import_module("vertexai.generative_models")
            GenerativeModel = getattr(generative_models, "GenerativeModel")
        except Exception as exc:
            return make_result(
                False,
                f"No se encontro dependencia de Vertex AI: {exc}",
                error_code="missing_vertex_dependency",
            )

        try:
            vertexai.init(project=project, location=location)
            model_instance = GenerativeModel(final_model, system_instruction=system_role)
            response = model_instance.generate_content(
                user_content,
                generation_config={"temperature": temp},
            )
            content = (getattr(response, "text", "") or "").strip()
            if not content:
                return make_result(
                    False,
                    "Vertex AI no devolvio contenido de texto.",
                    error_code="empty_response",
                )
            return make_result(True, "LLM response OK.", data={"content": content})
        except Exception as exc:
            return make_result(False, f"Error de Vertex AI: {exc}", error_code="vertex_error")
