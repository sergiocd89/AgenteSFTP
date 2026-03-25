import io
import importlib
import os
import sys
import types
import zipfile


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class UploadedFileStub:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def getvalue(self) -> bytes:
        return self._content


def _install_streamlit_stub():
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.cache_resource = lambda fn: fn
    streamlit_stub.cache_data = lambda fn: fn
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
