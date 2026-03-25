from core import perfil
import pytest


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


class _FakeStreamlit:
    def __init__(self, initial_state=None, checkbox_values=None):
        self.session_state = _SessionState(initial_state or {})
        self._checkbox_values = checkbox_values or {}
        self.errors = []
        self.infos = []
        self.successes = []

    def error(self, message):
        self.errors.append(message)

    def info(self, message):
        self.infos.append(message)

    def success(self, message):
        self.successes.append(message)

    def title(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None

    def divider(self, *args, **kwargs):
        return None

    def markdown(self, *args, **kwargs):
        return None

    def container(self, *args, **kwargs):
        return _Ctx()

    def columns(self, specs):
        return [_Ctx() for _ in specs]

    def checkbox(self, label, value=False, key=None):
        return self._checkbox_values.get(key, value)


def test_get_user_modules_and_access(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)

    modules = perfil.get_user_modules("sergio.cuevas.d")
    assert "SFTP" in modules
    assert perfil.has_module_access("sergio.cuevas.d", "DTSX") is True
    assert perfil.has_module_access("carlos.ramirez", "COBOL") is False
    assert perfil.get_user_modules("no.existe") == []


def test_has_module_access_rejects_unknown_module(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)

    with pytest.raises(ValueError):
        perfil.has_module_access("sergio.cuevas.d", "DESCONOCIDO")


def test_is_admin():
    assert perfil.is_admin("sergio.cuevas.d") is True
    assert perfil.is_admin("carlos.ramirez") is False


def test_show_profile_admin_denies_non_admin(monkeypatch):
    fake_st = _FakeStreamlit(initial_state={"username": "carlos.ramirez"})
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)

    perfil.show_profile_admin()

    assert any("No tienes permisos" in msg for msg in fake_st.errors)


def test_show_profile_admin_admin_no_changes(monkeypatch):
    fake_st = _FakeStreamlit(initial_state={"username": "sergio.cuevas.d"})
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)

    perfil.show_profile_admin()

    assert any("Sin cambios" in msg for msg in fake_st.infos)


def test_show_profile_admin_admin_with_changes(monkeypatch):
    fake_st = _FakeStreamlit(
        initial_state={"username": "sergio.cuevas.d"},
        checkbox_values={"profile_sergio.cuevas.d_COBOL": False},
    )
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)

    perfil.show_profile_admin()

    updated = fake_st.session_state.user_profiles["sergio.cuevas.d"]
    assert "COBOL" not in updated
    assert any("Cambios guardados" in msg for msg in fake_st.successes)


def test_init_profiles_uses_env_profiles_and_admins(monkeypatch):
    fake_st = _FakeStreamlit(initial_state={})
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)
    monkeypatch.setenv(
        "USER_PROFILES_JSON",
        '{"alice":["SFTP","Documentation"],"bob":["RequirementWorkflow"]}',
    )
    monkeypatch.setenv("ADMINS_CSV", "alice")

    perfil._init_profiles()

    assert fake_st.session_state.user_profiles["alice"] == ["SFTP", "Documentation"]
    assert fake_st.session_state.user_profiles["bob"] == ["RequirementWorkflow"]
    assert perfil.is_admin("alice") is True
    assert perfil.is_admin("bob") is False


def test_init_profiles_falls_back_when_env_is_invalid(monkeypatch):
    fake_st = _FakeStreamlit(initial_state={})
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)
    monkeypatch.setenv("USER_PROFILES_JSON", "{bad-json")
    monkeypatch.delenv("ADMINS_CSV", raising=False)

    perfil._init_profiles()

    assert "sergio.cuevas.d" in fake_st.session_state.user_profiles
    assert perfil.is_admin("sergio.cuevas.d") is True