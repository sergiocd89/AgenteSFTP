from fastapi.testclient import TestClient

from AgenteSFTPBackend.app.main import app
from AgenteSFTPBackend.app.security import create_access_token
from AgenteSFTPBackend.app.routers import integrations as integrations_router


def _auth_header(username: str = "sergio", modules: list[str] | None = None) -> dict[str, str]:
    token, _ = create_access_token(username, modules or ["RequirementWorkflow", "Documentation"], False)
    return {"Authorization": f"Bearer {token}"}


def test_jira_issue_success(monkeypatch):
    monkeypatch.setattr(integrations_router, "can_access_module", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        integrations_router,
        "create_jira_issue",
        lambda **_kwargs: {
            "success": True,
            "message": "ok",
            "data": {"issue_key": "ABC-1", "browse_url": "http://jira/browse/ABC-1"},
            "error_code": None,
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/integrations/jira/issue",
        headers=_auth_header(modules=["RequirementWorkflow"]),
        json={
            "base_url": "https://jira.example.com",
            "project_key": "ABC",
            "issue_type": "Story",
            "summary": "Demo",
            "description_text": "Body",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["issue_key"] == "ABC-1"


def test_jira_issue_forbidden_without_requirement_access(monkeypatch):
    monkeypatch.setattr(integrations_router, "can_access_module", lambda *_args, **_kwargs: False)

    client = TestClient(app)
    response = client.post(
        "/api/v1/integrations/jira/issue",
        headers=_auth_header(modules=["Documentation"]),
        json={
            "base_url": "https://jira.example.com",
            "project_key": "ABC",
            "issue_type": "Story",
            "summary": "Demo",
            "description_text": "Body",
        },
    )

    assert response.status_code == 403


def test_confluence_publish_success(monkeypatch):
    monkeypatch.setattr(integrations_router, "can_access_module", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        integrations_router,
        "create_confluence_page",
        lambda **_kwargs: {
            "success": True,
            "message": "ok",
            "data": {"page_url": "https://conf/wiki/x/123"},
            "error_code": None,
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/integrations/confluence/publish",
        headers=_auth_header(modules=["Documentation"]),
        json={
            "title": "Doc",
            "markdown_content": "# Demo",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "page_url" in payload["data"]


def test_confluence_metadata_success_with_requirement_access(monkeypatch):
    def _can_access(_username, module_key):
        return module_key == "RequirementWorkflow"

    monkeypatch.setattr(integrations_router, "can_access_module", _can_access)
    monkeypatch.setattr(
        integrations_router,
        "get_confluence_metadata",
        lambda **_kwargs: {
            "success": True,
            "message": "ok",
            "data": {"page_id": "123", "space_key": "ABC"},
            "error_code": None,
        },
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/integrations/confluence/metadata",
        headers=_auth_header(modules=["RequirementWorkflow"]),
        json={
            "page_url": "https://conf/wiki/pages/viewpage.action?pageId=123",
            "user": "u",
            "api_token": "t",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["page_id"] == "123"


def test_confluence_metadata_forbidden_without_required_modules(monkeypatch):
    monkeypatch.setattr(integrations_router, "can_access_module", lambda *_args, **_kwargs: False)

    client = TestClient(app)
    response = client.post(
        "/api/v1/integrations/confluence/metadata",
        headers=_auth_header(modules=["SFTP"]),
        json={
            "page_url": "https://conf/wiki/pages/viewpage.action?pageId=123",
            "user": "u",
            "api_token": "t",
        },
    )

    assert response.status_code == 403
