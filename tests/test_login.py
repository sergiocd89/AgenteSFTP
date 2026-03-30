from core import login
import pytest
import time


class _SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _StopCalled(Exception):
    pass


class _RerunCalled(Exception):
    pass


class _FakeStreamlit:
    def __init__(self, initial_state=None, text_inputs=None, submitted=False, logout_click=False):
        self.session_state = _SessionState(initial_state or {})
        self._text_inputs = list(text_inputs or [])
        self._submitted = submitted
        self._logout_click = logout_click
        self.errors = []
        self.successes = []
        self.warnings = []

    def markdown(self, *args, **kwargs):
        return None

    def title(self, *args, **kwargs):
        return None

    def subheader(self, *args, **kwargs):
        return None

    def divider(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None

    def columns(self, specs):
        return [_Ctx() for _ in specs]

    def container(self, *args, **kwargs):
        return _Ctx()

    def form(self, *args, **kwargs):
        return _Ctx()

    def expander(self, *args, **kwargs):
        return _Ctx()

    def text_input(self, *args, **kwargs):
        if self._text_inputs:
            return self._text_inputs.pop(0)
        return ""

    def form_submit_button(self, *args, **kwargs):
        return self._submitted

    def error(self, message):
        self.errors.append(message)

    def success(self, message):
        self.successes.append(message)

    def warning(self, message):
        self.warnings.append(message)

    def stop(self):
        raise _StopCalled()

    def rerun(self):
        raise _RerunCalled()

    def button(self, *args, **kwargs):
        return self._logout_click


def test_init_auth_state_sets_defaults(monkeypatch):
    fake_st = _FakeStreamlit(initial_state={})
    monkeypatch.setattr(login, "st", fake_st, raising=True)

    login._init_auth_state()

    assert fake_st.session_state.logged_in is False
    assert fake_st.session_state.username == ""
    assert fake_st.session_state.login_error is False


def test_normalize_login_inputs_requires_username():
    with pytest.raises(ValueError):
        login._normalize_login_inputs("   ", "secret")


def test_normalize_login_inputs_requires_password():
    with pytest.raises(ValueError):
        login._normalize_login_inputs("user.demo", "")


def test_show_login_returns_if_already_logged(monkeypatch):
    fake_st = _FakeStreamlit(initial_state={"logged_in": True, "username": "user", "login_error": False})
    monkeypatch.setattr(login, "st", fake_st, raising=True)

    login.show_login()

    assert fake_st.session_state.logged_in is True


def test_show_login_success_sets_session_and_rerun(monkeypatch):
    fake_st = _FakeStreamlit(text_inputs=[" user.demo ", "secret"], submitted=True)
    monkeypatch.setattr(login, "st", fake_st, raising=True)
    monkeypatch.setattr(login, "check_credentials", lambda username, password: True, raising=True)

    try:
        login.show_login()
    except _RerunCalled:
        pass

    assert fake_st.session_state.logged_in is True
    assert fake_st.session_state.username == "user.demo"
    assert fake_st.session_state.login_error is False


def test_show_login_failure_sets_error_and_stops(monkeypatch):
    fake_st = _FakeStreamlit(text_inputs=["user.demo", "bad"], submitted=True)
    monkeypatch.setattr(login, "st", fake_st, raising=True)
    monkeypatch.setattr(login, "check_credentials", lambda username, password: False, raising=True)

    try:
        login.show_login()
    except _StopCalled:
        pass

    assert fake_st.session_state.logged_in is False
    assert fake_st.session_state.login_error is True
    assert any("incorrectos" in msg for msg in fake_st.errors)


def test_render_logout_button_clears_session_and_rerun(monkeypatch):
    fake_st = _FakeStreamlit(
        initial_state={"username": "user.demo", "logged_in": True, "other": "value"},
        logout_click=True,
    )
    monkeypatch.setattr(login, "st", fake_st, raising=True)

    try:
        login.render_logout_button()
    except _RerunCalled:
        pass

    assert fake_st.session_state == {}


def test_render_change_password_section_success(monkeypatch):
    fake_st = _FakeStreamlit(
        initial_state={"username": "user.demo"},
        text_inputs=["old-pass", "new-pass", "new-pass"],
        submitted=True,
    )
    monkeypatch.setattr(login, "st", fake_st, raising=True)
    monkeypatch.setattr(login, "change_user_password", lambda *_args: (True, "Contraseña actualizada"), raising=True)

    login.render_change_password_section()

    assert any("actualizada" in msg for msg in fake_st.successes)


def test_render_change_password_section_confirm_mismatch(monkeypatch):
    fake_st = _FakeStreamlit(
        initial_state={"username": "user.demo"},
        text_inputs=["old-pass", "new-pass", "other-pass"],
        submitted=True,
    )
    monkeypatch.setattr(login, "st", fake_st, raising=True)

    login.render_change_password_section()

    assert any("no coincide" in msg.lower() for msg in fake_st.errors)


def test_ensure_backend_token_fresh_refreshes_when_expiring(monkeypatch):
    fake_st = _FakeStreamlit(
        initial_state={
            "backend_access_token": "old-token",
            "backend_profile": {},
            "backend_token_expires_at": time.time() - 10,
        }
    )
    monkeypatch.setattr(login, "st", fake_st, raising=True)
    monkeypatch.setattr(login.backend_api_client, "is_backend_enabled", lambda: True, raising=True)
    monkeypatch.setattr(
        login.backend_api_client,
        "refresh_access_token",
        lambda _token: (
            True,
            "ok",
            {
                "access_token": "new-token",
                "expires_in": 300,
                "modules": ["SFTP"],
                "is_admin": True,
            },
        ),
        raising=True,
    )

    assert login.ensure_backend_token_fresh() is True
    assert fake_st.session_state.backend_access_token == "new-token"
    assert fake_st.session_state.backend_profile["is_admin"] is True


def test_ensure_backend_token_fresh_keeps_token_if_not_expiring(monkeypatch):
    fake_st = _FakeStreamlit(
        initial_state={
            "backend_access_token": "same-token",
            "backend_profile": {},
            "backend_token_expires_at": time.time() + 600,
        }
    )
    monkeypatch.setattr(login, "st", fake_st, raising=True)
    monkeypatch.setattr(login.backend_api_client, "is_backend_enabled", lambda: True, raising=True)
    monkeypatch.setattr(
        login.backend_api_client,
        "refresh_access_token",
        lambda _token: (_ for _ in ()).throw(AssertionError("refresh should not be called")),
        raising=True,
    )

    assert login.ensure_backend_token_fresh() is True
    assert fake_st.session_state.backend_access_token == "same-token"


def test_run_backend_operation_with_retry_on_auth_error(monkeypatch):
    fake_st = _FakeStreamlit(
        initial_state={
            "backend_access_token": "old-token",
            "backend_profile": {},
            "backend_token_expires_at": time.time() + 600,
        }
    )
    monkeypatch.setattr(login, "st", fake_st, raising=True)
    monkeypatch.setattr(login.backend_api_client, "is_backend_enabled", lambda: True, raising=True)

    attempts = {"n": 0}

    def _op(token):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return False, "Sesión inválida o expirada. Vuelve a iniciar sesión."
        return True, f"ok:{token}"

    def _refresh_access_token(_token):
        return True, "ok", {
            "access_token": "new-token",
            "expires_in": 300,
            "modules": ["SFTP"],
            "is_admin": False,
        }

    monkeypatch.setattr(login.backend_api_client, "refresh_access_token", _refresh_access_token, raising=True)

    ok, payload = login.run_backend_operation_with_retry(_op)

    assert ok is True
    assert payload == "ok:new-token"
    assert attempts["n"] == 2


def test_render_backend_session_status_warns_when_backend_token_invalid(monkeypatch):
    fake_st = _FakeStreamlit(initial_state={"logged_in": True, "backend_access_token": ""})
    monkeypatch.setattr(login, "st", fake_st, raising=True)
    monkeypatch.setattr(login.backend_api_client, "is_backend_enabled", lambda: True, raising=True)
    monkeypatch.setattr(login, "ensure_backend_token_fresh", lambda **_kwargs: False, raising=True)

    login.render_backend_session_status()

    assert any("token válido" in msg for msg in fake_st.warnings)


def test_render_backend_session_status_noop_when_backend_disabled(monkeypatch):
    fake_st = _FakeStreamlit(initial_state={"logged_in": True})
    monkeypatch.setattr(login, "st", fake_st, raising=True)
    monkeypatch.setattr(login.backend_api_client, "is_backend_enabled", lambda: False, raising=True)

    login.render_backend_session_status()

    assert fake_st.warnings == []