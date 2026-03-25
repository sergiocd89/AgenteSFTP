import io
import urllib.error

from core import jira


def test_token_auth_returns_base64_string():
    token = jira._token_auth("user", "pass")
    assert token == "dXNlcjpwYXNz"


def test_create_jira_issue_requires_base_url_and_project_key():
    result = jira.create_jira_issue("", "", "Story", "sum", "desc")
    assert result["success"] is False
    assert "URL de Jira" in result["message"]


def test_create_jira_issue_requires_valid_url():
    result = jira.create_jira_issue(
        "ftp://example.atlassian.net",
        "PROJ",
        "Story",
        "summary",
        "description",
        "user@example.com",
        "token",
    )
    assert result["success"] is False
    assert "URL de Jira" in result["message"]


def test_create_jira_issue_requires_issue_type_and_summary():
    result = jira.create_jira_issue(
        "https://example.atlassian.net",
        "PROJ",
        "",
        "",
        "description",
        "user@example.com",
        "token",
    )
    assert result["success"] is False
    assert "Issue Type" in result["message"]


def test_create_jira_issue_requires_credentials(monkeypatch):
    monkeypatch.delenv("JIRA_USER", raising=False)
    monkeypatch.delenv("JIRA_PASSWORD", raising=False)

    result = jira.create_jira_issue(
        "https://example.atlassian.net",
        "PROJ",
        "Story",
        "summary",
        "description",
    )
    assert result["success"] is False
    assert "JIRA_USER" in result["message"]


def test_create_jira_issue_success(monkeypatch):
    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"key":"PROJ-123"}'

    monkeypatch.setattr(jira.urllib.request, "urlopen", lambda req, timeout=30, **kwargs: DummyResponse())

    result = jira.create_jira_issue(
        "https://example.atlassian.net",
        "PROJ",
        "Story",
        "summary",
        "description",
        "user@example.com",
        "token",
    )

    assert result["success"] is True
    assert "PROJ-123" in result["message"]
    assert result["data"]["issue_key"] == "PROJ-123"


def test_create_jira_issue_http_error(monkeypatch):
    def _raise_http_error(req, timeout=30, **kwargs):
        raise urllib.error.HTTPError(
            url="https://example.atlassian.net/rest/api/3/issue",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"invalid"}'),
        )

    monkeypatch.setattr(jira.urllib.request, "urlopen", _raise_http_error)

    result = jira.create_jira_issue(
        "https://example.atlassian.net",
        "PROJ",
        "Story",
        "summary",
        "description",
        "user@example.com",
        "token",
    )

    assert result["success"] is False
    assert "HTTP 400" in result["message"]
    assert result["error_code"] == "http_error"


def test_create_jira_issue_invalid_json(monkeypatch):
    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"{invalid-json"

    monkeypatch.setattr(jira.urllib.request, "urlopen", lambda req, timeout=30, **kwargs: DummyResponse())

    result = jira.create_jira_issue(
        "https://example.atlassian.net",
        "PROJ",
        "Story",
        "summary",
        "description",
        "user@example.com",
        "token",
    )

    assert result["success"] is False
    assert "JSON" in result["message"]
    assert result["error_code"] == "invalid_json"
