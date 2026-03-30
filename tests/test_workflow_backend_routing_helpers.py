import importlib
import os
import sys
import types


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _install_streamlit_stub():
    streamlit_stub = types.ModuleType("streamlit")

    def _cache_decorator_stub(*dargs, **dkwargs):
        if dargs and callable(dargs[0]) and len(dargs) == 1 and not dkwargs:
            return dargs[0]
        return lambda fn: fn

    streamlit_stub.cache_resource = _cache_decorator_stub
    streamlit_stub.cache_data = _cache_decorator_stub
    streamlit_stub.session_state = SessionState({"model_name": "gpt-4o", "temp": 0.0})

    def _noop(*args, **kwargs):
        return None

    for name in [
        "error",
        "stop",
        "markdown",
        "divider",
        "title",
        "caption",
        "warning",
        "success",
        "info",
    ]:
        setattr(streamlit_stub, name, _noop)

    sys.modules["streamlit"] = streamlit_stub


def _import_module(module_name: str):
    _install_streamlit_stub()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.append(root)
    return importlib.import_module(module_name)


def _assert_backend_path(module, workflow: str, step: str, monkeypatch):
    module.st.session_state["backend_access_token"] = "token"
    module.st.session_state["model_name"] = "gpt-4o"
    module.st.session_state["temp"] = 0.0

    called = {}

    monkeypatch.setattr(module.backend_api_client, "is_backend_enabled", lambda: True)

    def _fake_retry(operation):
        return operation("token")

    monkeypatch.setattr(module, "run_backend_operation_with_retry", _fake_retry)

    log_calls = []

    def _fake_log_operation(logger, operation, success, error_code=None, details=None):
        log_calls.append(
            {
                "operation": operation,
                "success": success,
                "error_code": error_code,
                "details": details,
            }
        )

    monkeypatch.setattr(module, "log_operation", _fake_log_operation)

    def _fake_execute(**kwargs):
        called.update(kwargs)
        return True, {"content": "backend-output"}

    monkeypatch.setattr(module.backend_api_client, "execute_workflow_step", _fake_execute)

    out = module._run_workflow_step(step, "any_prompt.md", "input-data", "ctx")

    assert out == "backend-output"
    assert called["workflow"] == workflow
    assert called["step"] == step
    assert log_calls
    assert log_calls[-1]["operation"] == "workflow_step_backend"
    assert log_calls[-1]["success"] is True
    assert f"workflow={workflow}" in str(log_calls[-1]["details"])
    assert f"step={step}" in str(log_calls[-1]["details"])


def _assert_fallback_path(module, step: str, monkeypatch):
    monkeypatch.setattr(module.backend_api_client, "is_backend_enabled", lambda: False)
    monkeypatch.setattr(module, "load_agent_prompt", lambda _prompt: "sys")
    monkeypatch.setattr(module, "run_llm_text", lambda *_args, **_kwargs: "local-output")

    out = module._run_workflow_step(step, "any_prompt.md", "input-data", "ctx")

    assert out == "local-output"


def test_sftp_routing_backend_and_fallback(monkeypatch):
    module = _import_module("modules.modulo_sftp")
    _assert_backend_path(module, "sftp", "analyze", monkeypatch)
    _assert_fallback_path(module, "audit", monkeypatch)


def test_cobol_routing_backend_and_fallback(monkeypatch):
    module = _import_module("modules.modulo_cobol")
    _assert_backend_path(module, "cobol_python", "analyze", monkeypatch)
    _assert_fallback_path(module, "develop", monkeypatch)


def test_dtsx_routing_backend_and_fallback(monkeypatch):
    module = _import_module("modules.modulo_dtsx")
    _assert_backend_path(module, "cobol_dtsx", "architect", monkeypatch)
    _assert_fallback_path(module, "audit", monkeypatch)
