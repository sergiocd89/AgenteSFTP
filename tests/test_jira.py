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


def test_create_jira_issue_retries_after_429_and_succeeds(monkeypatch):
    calls = {"count": 0}
    sleep_calls = []

    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"key":"PROJ-456"}'

    def _urlopen_with_429_then_success(req, timeout=30, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.HTTPError(
                url="https://example.atlassian.net/rest/api/3/issue",
                code=429,
                msg="Too Many Requests",
                hdrs={"Retry-After": "1.5"},
                fp=io.BytesIO(b'{"error":"rate_limited"}'),
            )
        return DummyResponse()

    monkeypatch.setenv("HTTP_MAX_RETRIES", "2")
    monkeypatch.setattr(jira.urllib.request, "urlopen", _urlopen_with_429_then_success)
    monkeypatch.setattr(jira.time, "sleep", lambda seconds: sleep_calls.append(seconds))

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
    assert result["data"]["issue_key"] == "PROJ-456"
    assert calls["count"] == 2
    assert sleep_calls == [1.5]


def test_compute_retry_delay_uses_backoff_when_retry_after_invalid(monkeypatch):
    monkeypatch.setattr(jira.random, "uniform", lambda a, b: 0.1)

    delay = jira._compute_retry_delay(attempt=1, backoff=0.5, retry_after="invalid")

    assert delay == 1.1
