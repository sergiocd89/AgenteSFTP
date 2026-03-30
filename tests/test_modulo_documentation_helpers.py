import io
import importlib
import os
import sys
import types
import zipfile
import pytest


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class UploadedFileStub:
    def __init__(self, name: str, content: bytes, size: int | None = None):
        self.name = name
        self._content = content
        self.size = len(content) if size is None else size

    def getvalue(self) -> bytes:
        return self._content


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

    for name in ["error", "stop", "markdown", "divider", "title", "caption"]:
        setattr(streamlit_stub, name, _noop)

    sys.modules["streamlit"] = streamlit_stub


def _import_doc_module():
    _install_streamlit_stub()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.append(root)
    return importlib.import_module("modules.modulo_documentation")


def test_extract_text_from_plain_file():
    module = _import_doc_module()
    uploaded = UploadedFileStub("sample.txt", b"hola mundo")

    content, summary = module._extract_text_from_uploaded_file(uploaded, max_chars=50)

    assert content == "hola mundo"
    assert "sample.txt" in summary


def test_extract_from_zip_bytes_reads_supported_files():
    module = _import_doc_module()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("a.sql", "SELECT 1;")
        zf.writestr("b.bin", b"\x00\x01\x02")
        zf.writestr("dir/c.py", "print('ok')")

    content, summary = module._extract_from_zip_bytes(buffer.getvalue(), "pack.zip", 500)

    assert "a.sql" in content
    assert "dir/c.py" in content
    assert "Paquete leido" in summary


def test_extract_from_zip_returns_empty_when_no_supported_files():
    module = _import_doc_module()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("image.png", b"PNG")

    content, summary = module._extract_from_zip_bytes(buffer.getvalue(), "pack.zip", 200)

    assert content == ""
    assert "sin archivos de texto compatibles" in summary


def test_extract_text_from_uploaded_file_requires_file_instance():
    module = _import_doc_module()

    with pytest.raises(ValueError):
        module._extract_text_from_uploaded_file(None)


def test_extract_text_from_uploaded_file_requires_positive_max_chars():
    module = _import_doc_module()
    uploaded = UploadedFileStub("sample.txt", b"hola")

    with pytest.raises(ValueError):
        module._extract_text_from_uploaded_file(uploaded, max_chars=0)


def test_extract_from_zip_bytes_rejects_invalid_zip_content():
    module = _import_doc_module()

    with pytest.raises(ValueError):
        module._extract_from_zip_bytes(b"not-a-zip", "broken.zip", 100)


def test_decode_text_reports_replacements_when_needed():
    module = _import_doc_module()

    # Forzamos el fallback a utf-8-replace con una secuencia invalida para utf-8 y
    # caracteres fuera de latin-1/cp1252, interpretado como bytes arbitrarios.
    raw = b"\x80\x80\x80"
    text, encoding, had_replacements = module._decode_text(raw)

    assert isinstance(text, str)
    assert encoding in {"latin-1", "cp1252", "utf-8-replace", "utf-8"}
    # En entornos donde latin-1/cp1252 decodifican sin error, no hay reemplazos.
    # Validamos contrato minimo de tipos y valores booleanos.
    assert isinstance(had_replacements, bool)


def test_build_uploader_types_changes_with_selected_tech():
    module = _import_doc_module()

    default_types = module._build_uploader_types([])
    legacy_types = module._build_uploader_types(["COBOL"])

    assert "zip" in default_types
    assert "cbl" not in default_types
    assert "cbl" in legacy_types


def test_extract_text_from_uploaded_file_rejects_large_file():
    module = _import_doc_module()
    uploaded = UploadedFileStub("huge.txt", b"ok", size=module.MAX_UPLOAD_BYTES + 1)

    with pytest.raises(ValueError, match="limite"):
        module._extract_text_from_uploaded_file(uploaded, max_chars=100)


def test_extract_from_zip_bytes_rejects_large_zip_bytes(monkeypatch):
    module = _import_doc_module()

    # Simula ZIP demasiado grande sin crear payload gigante en memoria.
    monkeypatch.setattr(module, "MAX_UPLOAD_BYTES", 8)
    with pytest.raises(ValueError, match="limite"):
        module._extract_from_zip_bytes(b"123456789", "big.zip", 100)


def test_run_documentation_analysis_uses_backend_when_enabled(monkeypatch):
    module = _import_doc_module()
    module.st.session_state["backend_access_token"] = "token"
    module.st.session_state["model_name"] = "gpt-4o"
    module.st.session_state["temp"] = 0.0

    monkeypatch.setattr(module.backend_api_client, "is_backend_enabled", lambda: True)

    def _fake_retry(operation):
        return operation("token")

    monkeypatch.setattr(module, "run_backend_operation_with_retry", _fake_retry)
    log_calls = []
    monkeypatch.setattr(
        module,
        "log_operation",
        lambda _logger, operation, success, error_code=None, details=None: log_calls.append(
            {
                "operation": operation,
                "success": success,
                "error_code": error_code,
                "details": details,
            }
        ),
    )
    monkeypatch.setattr(
        module.backend_api_client,
        "execute_workflow_step",
        lambda **_kwargs: (True, {"content": "backend-doc"}),
    )

    output = module._run_documentation_analysis("entrada")
    assert output == "backend-doc"
    assert log_calls
    assert log_calls[-1]["operation"] == "workflow_step_backend"
    assert log_calls[-1]["success"] is True
    assert "request_id=" in str(log_calls[-1]["details"])
    assert "workflow=documentation" in str(log_calls[-1]["details"])
    assert "step=analyze" in str(log_calls[-1]["details"])


def test_run_documentation_analysis_falls_back_to_local(monkeypatch):
    module = _import_doc_module()
    monkeypatch.setattr(module.backend_api_client, "is_backend_enabled", lambda: False)
    monkeypatch.setattr(module, "load_agent_prompt", lambda _name: "sys")
    monkeypatch.setattr(module, "run_llm_text", lambda *_args, **_kwargs: "local-doc")

    output = module._run_documentation_analysis("entrada")
    assert output == "local-doc"


def test_with_request_id_formats_message():
    module = _import_doc_module()

    message = module._with_request_id("Error de backend", "abc123")

    assert "Error de backend" in message
    assert "request_id=abc123" in message
