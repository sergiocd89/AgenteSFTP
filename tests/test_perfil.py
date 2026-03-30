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

    def expander(self, *args, **kwargs):
        return _Ctx()

    def form(self, *args, **kwargs):
        return _Ctx()

    def columns(self, specs):
        return [_Ctx() for _ in specs]

    def text_input(self, *args, **kwargs):
        return kwargs.get("value", "")

    def multiselect(self, *args, **kwargs):
        return kwargs.get("default", [])

    def form_submit_button(self, *args, **kwargs):
        return False

    def button(self, *args, **kwargs):
        return False

    def checkbox(self, label, value=False, key=None):
        return self._checkbox_values.get(key, value)

    def rerun(self):
        return None


def test_get_user_modules_and_access(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)
    monkeypatch.setenv(
        "USER_PROFILES_JSON",
        '{"sergio.cuevas.d":["SFTP","COBOL","DTSX","RequirementWorkflow","Documentation"],"carlos.ramirez":["SFTP","RequirementWorkflow","Documentation"]}',
    )
    monkeypatch.setenv("ADMINS_CSV", "sergio.cuevas.d")

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


def test_is_admin(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)
    monkeypatch.setenv(
        "USER_PROFILES_JSON",
        '{"sergio.cuevas.d":["SFTP","COBOL","DTSX","RequirementWorkflow","Documentation"],"carlos.ramirez":["SFTP","RequirementWorkflow","Documentation"]}',
    )
    monkeypatch.setenv("ADMINS_CSV", "sergio.cuevas.d")

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
    monkeypatch.setenv(
        "USER_PROFILES_JSON",
        '{"sergio.cuevas.d":["SFTP","COBOL","DTSX","RequirementWorkflow","Documentation"],"carlos.ramirez":["SFTP","RequirementWorkflow","Documentation"]}',
    )
    monkeypatch.setenv("ADMINS_CSV", "sergio.cuevas.d")

    perfil.show_profile_admin()

    assert any("Sin cambios" in msg for msg in fake_st.infos)


def test_show_profile_admin_admin_with_changes(monkeypatch):
    fake_st = _FakeStreamlit(
        initial_state={"username": "sergio.cuevas.d"},
        checkbox_values={"profile_sergio.cuevas.d_COBOL": False},
    )
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)
    monkeypatch.setenv(
        "USER_PROFILES_JSON",
        '{"sergio.cuevas.d":["SFTP","COBOL","DTSX","RequirementWorkflow","Documentation"],"carlos.ramirez":["SFTP","RequirementWorkflow","Documentation"]}',
    )
    monkeypatch.setenv("ADMINS_CSV", "sergio.cuevas.d")

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

    assert fake_st.session_state.user_profiles == {}
    assert perfil.is_admin("sergio.cuevas.d") is False


def test_load_profiles_and_admins_from_postgres(monkeypatch):
    class _FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *_args, **_kwargs):
            return None

        def fetchall(self):
            return [
                ("sergio.cuevas.d", "SFTP", True),
                ("sergio.cuevas.d", "DTSX", True),
                ("carlos.ramirez", "Documentation", False),
            ]

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return _FakeCursor()

    class _FakePsycopg:
        @staticmethod
        def connect(_dsn):
            return _FakeConn()

    monkeypatch.setattr(perfil, "psycopg", _FakePsycopg, raising=True)
    monkeypatch.setenv("AUTH_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    loaded = perfil._build_profile_service().load_profiles_and_admins_from_postgres()
    assert loaded is not None
    profiles, admins = loaded
    assert profiles["sergio.cuevas.d"] == ["SFTP", "DTSX"]
    assert profiles["carlos.ramirez"] == ["Documentation"]
    assert "sergio.cuevas.d" in admins


def test_profile_service_update_user_profile_postgres(monkeypatch):
    class _FakeCursor:
        def __init__(self):
            self._last_select = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params=None):
            if "SELECT id FROM app_auth.app_user" in query:
                self._last_select = True
            self.query = query
            self.params = params

        def fetchone(self):
            if self._last_select:
                return (1,)
            return None

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return _FakeCursor()

        def commit(self):
            return None

    class _FakePsycopg:
        @staticmethod
        def connect(_dsn):
            return _FakeConn()

    monkeypatch.setattr(perfil, "psycopg", _FakePsycopg, raising=True)
    monkeypatch.setenv("AUTH_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    ok = perfil._build_profile_service().update_user_profile(
        username="sergio.cuevas.d",
        full_name="Sergio Cuevas",
        is_admin_user=True,
        is_active_user=True,
        module_keys=["SFTP", "COBOL"],
        actor="tester",
    )
    assert ok is True


def test_admin_reset_password_postgres(monkeypatch):
    class _FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *_args, **_kwargs):
            return None

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return _FakeCursor()

        def commit(self):
            return None

    class _FakePsycopg:
        @staticmethod
        def connect(_dsn):
            return _FakeConn()

    monkeypatch.setattr(perfil, "psycopg", _FakePsycopg, raising=True)
    monkeypatch.setenv("AUTH_PROVIDER", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    ok, _ = perfil._build_profile_service().admin_reset_password(
        username="sergio.cuevas.d",
        new_plain_password="Nueva#2026",
        actor="tester",
    )
    assert ok is True


def test_create_user_profile_env_success(monkeypatch):
    fake_st = _FakeStreamlit(initial_state={})
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)
    monkeypatch.setenv("AUTH_PROVIDER", "env")

    ok, _ = perfil.create_user_profile(
        username="nuevo.usuario",
        plain_password="Nueva#2026",
        full_name="Nuevo Usuario",
        is_admin_user=False,
        is_active_user=True,
        module_keys=["SFTP", "Documentation"],
        actor="sergio.cuevas.d",
    )

    assert ok is True
    assert "nuevo.usuario" in fake_st.session_state.user_profiles


def test_create_user_profile_requires_username(monkeypatch):
    fake_st = _FakeStreamlit(initial_state={})
    monkeypatch.setattr(perfil, "st", fake_st, raising=True)

    ok, message = perfil.create_user_profile(
        username=" ",
        plain_password="Nueva#2026",
        full_name="Nuevo Usuario",
        is_admin_user=False,
        is_active_user=True,
        module_keys=["SFTP"],
        actor="sergio.cuevas.d",
    )

    assert ok is False
    assert "username" in message.lower()