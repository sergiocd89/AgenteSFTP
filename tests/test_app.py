import os
import sys
import types

# insert a minimal streamlit stub before importing app
streamlit_stub = types.ModuleType("streamlit")
# provide no-op functions used in app
for name in [
    'set_page_config', 'title', 'file_uploader', 'columns', 'subheader',
    'code', 'button', 'spinner', 'success', 'error', 'info',
    'text_input', 'selectbox'
]:
    setattr(streamlit_stub, name, lambda *a, **k: None)

# decorators used in core.utils
def _cache_decorator_stub(*dargs, **dkwargs):
    if dargs and callable(dargs[0]) and len(dargs) == 1 and not dkwargs:
        return dargs[0]
    return lambda fn: fn


streamlit_stub.cache_resource = _cache_decorator_stub
streamlit_stub.cache_data = _cache_decorator_stub

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

from modules import modulo_sftp


def test_modulo_sftp_exports_main_entrypoint():
    assert hasattr(modulo_sftp, "show_sftp_migration")
