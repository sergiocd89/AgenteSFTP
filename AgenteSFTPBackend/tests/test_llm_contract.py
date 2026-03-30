from fastapi.testclient import TestClient

from AgenteSFTPBackend.app.main import app
from AgenteSFTPBackend.app.security import create_access_token
from AgenteSFTPBackend.app.routers import llm as llm_router


def _auth_header() -> dict[str, str]:
    token, _ = create_access_token("sergio", ["SFTP"], False)
    return {"Authorization": f"Bearer {token}"}


def test_llm_generate_success_contract(monkeypatch):
    monkeypatch.setattr(
        llm_router,
        "generate_llm_text",
        lambda **_kwargs: {
            "success": True,
            "message": "ok",
            "data": {"content": "respuesta"},
            "error_code": None,
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/llm/generate",
        headers=_auth_header(),
        json={
            "system_role": "Analyst",
            "user_content": "hola",
            "model": "gpt-4o",
            "temp": 0.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["content"] == "respuesta"


def test_llm_generate_error_contract(monkeypatch):
    monkeypatch.setattr(
        llm_router,
        "generate_llm_text",
        lambda **_kwargs: {
            "success": False,
            "message": "provider down",
            "data": None,
            "error_code": "connection_error",
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/llm/generate",
        headers=_auth_header(),
        json={
            "system_role": "Analyst",
            "user_content": "hola",
            "model": "gpt-4o",
            "temp": 0.0,
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "connection_error"
