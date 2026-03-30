from fastapi.testclient import TestClient

from AgenteSFTPBackend.app.main import app
from AgenteSFTPBackend.app.security import create_access_token
from AgenteSFTPBackend.app.routers import workflows as workflows_router


def _auth_header(username: str = "sergio") -> dict[str, str]:
    token, _ = create_access_token(username, ["SFTP", "COBOL", "DTSX", "RequirementWorkflow", "Documentation"], True)
    return {"Authorization": f"Bearer {token}"}


def test_workflow_step_success(monkeypatch):
    monkeypatch.setattr(workflows_router, "get_workflow_module_key", lambda _workflow: "SFTP")
    monkeypatch.setattr(workflows_router, "can_access_module", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        workflows_router,
        "execute_workflow_step",
        lambda **_kwargs: {"success": True, "message": "ok", "data": {"content": "resultado"}, "error_code": None},
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/workflows/sftp/steps/analyze",
        headers=_auth_header(),
        json={"input": "source", "context": "ctx", "model": "gpt-4o", "temp": 0.0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["workflow"] == "sftp"
    assert payload["step"] == "analyze"
    assert payload["content"] == "resultado"


def test_workflow_step_forbidden_when_no_module_access(monkeypatch):
    monkeypatch.setattr(workflows_router, "get_workflow_module_key", lambda _workflow: "SFTP")
    monkeypatch.setattr(workflows_router, "can_access_module", lambda *_args, **_kwargs: False)

    client = TestClient(app)
    response = client.post(
        "/api/v1/workflows/sftp/steps/analyze",
        headers=_auth_header(),
        json={"input": "source", "context": "ctx", "model": "gpt-4o", "temp": 0.0},
    )

    assert response.status_code == 403


def test_workflow_step_returns_400_on_domain_error(monkeypatch):
    monkeypatch.setattr(workflows_router, "get_workflow_module_key", lambda _workflow: "SFTP")
    monkeypatch.setattr(workflows_router, "can_access_module", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        workflows_router,
        "execute_workflow_step",
        lambda **_kwargs: {
            "success": False,
            "message": "Step no soportado",
            "data": None,
            "error_code": "unsupported_step",
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/workflows/sftp/steps/unknown",
        headers=_auth_header(),
        json={"input": "source", "context": "ctx", "model": "gpt-4o", "temp": 0.0},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_code"] == "unsupported_step"


def test_workflow_unknown_returns_404(monkeypatch):
    monkeypatch.setattr(workflows_router, "get_workflow_module_key", lambda _workflow: None)

    client = TestClient(app)
    response = client.post(
        "/api/v1/workflows/unknown/steps/analyze",
        headers=_auth_header(),
        json={"input": "source", "context": "ctx", "model": "gpt-4o", "temp": 0.0},
    )

    assert response.status_code == 404
