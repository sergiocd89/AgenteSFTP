import io
import urllib.error

from core import confluence


def test_extract_page_id_from_link_query_param():
    url = "https://example.atlassian.net/wiki/pages/viewpage.action?pageId=12345"
    assert confluence._extract_page_id_from_link(url) == "12345"


def test_extract_page_id_from_link_path_format():
    url = "https://example.atlassian.net/wiki/spaces/ABC/pages/99999/Some+Page"
    assert confluence._extract_page_id_from_link(url) == "99999"


def test_get_confluence_page_metadata_requires_valid_link_and_credentials():
    ok, message = confluence.get_confluence_page_metadata_from_link("", "", "")
    assert not ok
    assert "link" in message.lower()


def test_get_confluence_page_metadata_success(monkeypatch):
    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return (
                b'{"id":"12345","title":"My Page","space":{"key":"ABC"},'
                b'"ancestors":[{"id":"222"}]}'
            )

    monkeypatch.setattr(confluence.urllib.request, "urlopen", lambda req, timeout=30: DummyResponse())

    ok, payload = confluence.get_confluence_page_metadata_from_link(
        "https://example.atlassian.net/wiki/pages/viewpage.action?pageId=12345",
        "user",
        "token",
    )

    assert ok
    assert payload["space_key"] == "ABC"
    assert payload["parent_id"] == "222"


def test_upload_markdown_to_confluence_requires_data(monkeypatch):
    monkeypatch.delenv("CONFLUENCE_BASE_URL", raising=False)
    monkeypatch.delenv("CONFLUENCE_SPACE_KEY", raising=False)
    monkeypatch.delenv("CONFLUENCE_USER", raising=False)
    monkeypatch.delenv("CONFLUENCE_API_TOKEN", raising=False)

    ok, message = confluence.upload_markdown_to_confluence("Title", "Body")
    assert not ok
    assert "CONFLUENCE_BASE_URL" in message


def test_upload_markdown_to_confluence_success(monkeypatch):
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://example.atlassian.net/wiki")

    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"_links":{"webui":"/spaces/ABC/pages/12345"}}'

    monkeypatch.setattr(confluence.urllib.request, "urlopen", lambda req, timeout=30: DummyResponse())

    ok, message = confluence.upload_markdown_to_confluence(
        "Title",
        "Body",
        parent_id="321",
        space_key="ABC",
        user="user",
        api_token="token",
    )

    assert ok
    assert "Documento subido" in message


def test_upload_markdown_to_confluence_http_error(monkeypatch):
    monkeypatch.setenv("CONFLUENCE_BASE_URL", "https://example.atlassian.net/wiki")

    def _raise_http_error(req, timeout=30):
        raise urllib.error.HTTPError(
            url="https://example.atlassian.net/wiki/rest/api/content",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"forbidden"}'),
        )

    monkeypatch.setattr(confluence.urllib.request, "urlopen", _raise_http_error)

    ok, message = confluence.upload_markdown_to_confluence(
        "Title",
        "Body",
        space_key="ABC",
        user="user",
        api_token="token",
    )

    assert not ok
    assert "HTTP 403" in message
