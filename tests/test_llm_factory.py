from core.infrastructure.llm.factory import resolve_llm_gateway
from core.infrastructure.llm.openai_gateway import OpenAILlmGateway
from core.infrastructure.llm.vertex_gateway import VertexLlmGateway


def test_resolve_llm_gateway_openai(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    gateway, provider = resolve_llm_gateway()
    assert provider == "openai"
    assert isinstance(gateway, OpenAILlmGateway)


def test_resolve_llm_gateway_vertex_alias(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "vertex_gemini")
    gateway, provider = resolve_llm_gateway()
    assert provider == "vertex_gemini"
    assert isinstance(gateway, VertexLlmGateway)


def test_resolve_llm_gateway_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown")
    gateway, provider = resolve_llm_gateway()
    assert provider == "unknown"
    assert gateway is None
