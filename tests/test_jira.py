import io
import urllib.error

from core import jira


def test_token_auth_returns_base64_string():
    token = jira._token_auth("user", "pass")
    assert token == "dXNlcjpwYXNz"


def test_create_jira_issue_requires_base_url_and_project_key():
    ok, message = jira.create_jira_issue("", "", "Story", "sum", "desc")
    assert not ok
    assert "URL de Jira" in message


def test_create_jira_issue_requires_credentials(monkeypatch):
    monkeypatch.delenv("JIRA_USER", raising=False)
    monkeypatch.delenv("JIRA_PASSWORD", raising=False)

    ok, message = jira.create_jira_issue(
        "https://example.atlassian.net",
        "PROJ",
        "Story",
        "summary",
        "description",
    )
    assert not ok
    assert "JIRA_USER" in message


def test_create_jira_issue_success(monkeypatch):
    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"key":"PROJ-123"}'

    monkeypatch.setattr(jira.urllib.request, "urlopen", lambda req, timeout=30: DummyResponse())

    ok, message = jira.create_jira_issue(
        "https://example.atlassian.net",
        "PROJ",
        "Story",
        "summary",
        "description",
        "user@example.com",
        "token",
    )

    assert ok
    assert "PROJ-123" in message


def test_create_jira_issue_http_error(monkeypatch):
    def _raise_http_error(req, timeout=30):
        raise urllib.error.HTTPError(
            url="https://example.atlassian.net/rest/api/3/issue",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"invalid"}'),
        )

    monkeypatch.setattr(jira.urllib.request, "urlopen", _raise_http_error)

    ok, message = jira.create_jira_issue(
        "https://example.atlassian.net",
        "PROJ",
        "Story",
        "summary",
        "description",
        "user@example.com",
        "token",
    )

    assert not ok
    assert "HTTP 400" in message
