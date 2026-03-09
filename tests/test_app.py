import os
import sys
import types
import pytest

# insert a minimal streamlit stub before importing app
streamlit_stub = types.ModuleType("streamlit")
# provide no-op functions used in app
for name in [
    'set_page_config', 'title', 'file_uploader', 'columns', 'subheader',
    'code', 'button', 'spinner', 'success', 'error', 'info',
    'text_input', 'selectbox'
]:
    setattr(streamlit_stub, name, lambda *a, **k: None)

# provide a simple session_state object that allows attribute access
class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
    def __setattr__(self, name, value):
        self[name] = value

streamlit_stub.session_state = SessionState()

# sidebar is used as context manager
class SidebarStub:
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb): return False
    def text_input(self, *a, **k): return None
    def selectbox(self, *a, **k): return None
setattr(streamlit_stub, 'sidebar', SidebarStub())

sys.modules['streamlit'] = streamlit_stub

# ensure workspace root is on sys.path so `app` can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import refactor_code


class DummyResponse:
    choices = [type("x", (), {"message": type("y", (), {"content": "dummy"})})]


class DummyChat:
    @staticmethod
    def create(*args, **kwargs):
        return DummyResponse()

class DummyClient:
    def __init__(self, api_key=None):
        pass
    chat = types.SimpleNamespace(completions=DummyChat)


def test_refactor_code(monkeypatch):
    # patch the OpenAI client class
    monkeypatch.setattr('openai.OpenAI', DummyClient)
    out = refactor_code("codigo de prueba", api_key="fake", model_name="gpt-4o")
    assert out == "dummy"
