from core.infrastructure import backend_api_client


def test_execute_workflow_step_returns_auth_message_on_401(monkeypatch):
    monkeypatch.setattr(
        backend_api_client,
        "_http_json",
        lambda *_args, **_kwargs: (False, 401, {"detail": "Not authenticated"}),
    )

    ok, payload = backend_api_client.execute_workflow_step(
        token="token",
        workflow="sftp",
        step="analyze",
        source_input="source",
        context="",
        model="gpt-4o",
        temp=0.0,
    )

    assert ok is False
    assert payload["message"] == "Sesión inválida o expirada. Vuelve a iniciar sesión."
    assert payload["error_code"] is None


def test_execute_workflow_step_uses_detail_error_when_non_auth(monkeypatch):
    monkeypatch.setattr(
        backend_api_client,
        "_http_json",
        lambda *_args, **_kwargs: (
            False,
            400,
            {"detail": {"message": "Step no soportado", "error_code": "unsupported_step"}},
        ),
    )

    ok, payload = backend_api_client.execute_workflow_step(
        token="token",
        workflow="requirement",
        step="invalid",
        source_input="source",
        context="",
        model="gpt-4o",
        temp=0.0,
    )

    assert ok is False
    assert payload["message"] == "Step no soportado"
    assert payload["error_code"] == "unsupported_step"


def test_execute_workflow_step_uses_step_specific_timeout(monkeypatch):
    monkeypatch.setenv("BACKEND_WORKFLOW_TIMEOUT_SECONDS", "40")
    monkeypatch.setenv("BACKEND_WORKFLOW_TIMEOUT_ANALYZE", "75")

    captured = {}

    def _fake_http_json(_method, _path, payload=None, token=None, timeout=0.0):
        captured["timeout"] = timeout
        return True, 200, {"content": "ok"}

    monkeypatch.setattr(backend_api_client, "_http_json", _fake_http_json)

    ok, payload = backend_api_client.execute_workflow_step(
        token="token",
        workflow="sftp",
        step="analyze",
        source_input="source",
        context="",
        model="gpt-4o",
        temp=0.0,
    )

    assert ok is True
    assert payload["content"] == "ok"
    assert captured["timeout"] == 75.0


def test_execute_workflow_step_uses_default_timeout_when_step_override_missing(monkeypatch):
    monkeypatch.setenv("BACKEND_WORKFLOW_TIMEOUT_SECONDS", "33")
    monkeypatch.delenv("BACKEND_WORKFLOW_TIMEOUT_ARCHITECT", raising=False)

    captured = {}

    def _fake_http_json(_method, _path, payload=None, token=None, timeout=0.0):
        captured["timeout"] = timeout
        return True, 200, {"content": "ok"}

    monkeypatch.setattr(backend_api_client, "_http_json", _fake_http_json)

    ok, payload = backend_api_client.execute_workflow_step(
        token="token",
        workflow="sftp",
        step="architect",
        source_input="source",
        context="",
        model="gpt-4o",
        temp=0.0,
    )

    assert ok is True
    assert payload["content"] == "ok"
    assert captured["timeout"] == 33.0
