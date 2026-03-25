from core.domain.ai_service import call_llm


class DummyGatewaySuccess:
    def generate(self, system_role: str, user_content: str, model: str, temp: float) -> dict:
        return {
            "success": True,
            "message": "ok",
            "data": {"content": "respuesta"},
            "error_code": None,
        }


class DummyGatewayFailure:
    def generate(self, system_role: str, user_content: str, model: str, temp: float) -> dict:
        return {
            "success": False,
            "message": "fallo controlado",
            "data": None,
            "error_code": "provider_error",
        }


def test_call_llm_requires_gateway():
    result = call_llm("sys", "user", "gpt-4o", 0.0)
    assert result["success"] is False
    assert result["error_code"] == "missing_gateway"


def test_call_llm_success_with_gateway():
    result = call_llm("sys", "user", "gpt-4o", 0.0, llm_gateway=DummyGatewaySuccess())
    assert result["success"] is True
    assert result["data"]["content"] == "respuesta"


def test_call_llm_failure_from_gateway():
    result = call_llm("sys", "user", "gpt-4o", 0.0, llm_gateway=DummyGatewayFailure())
    assert result["success"] is False
    assert result["error_code"] == "provider_error"
