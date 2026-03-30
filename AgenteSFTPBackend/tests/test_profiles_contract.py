from fastapi.testclient import TestClient

from AgenteSFTPBackend.app.main import app
from AgenteSFTPBackend.app.security import create_access_token
from AgenteSFTPBackend.app.routers import profiles as profiles_router


def _auth_header(username: str = "sergio", modules: list[str] | None = None, is_admin: bool = False) -> dict[str, str]:
    token, _ = create_access_token(username, modules or ["SFTP"], is_admin)
    return {"Authorization": f"Bearer {token}"}


def _profile(username: str, is_admin: bool = False) -> dict:
    return {
        "username": username,
        "modules": ["SFTP", "COBOL"],
        "is_admin": is_admin,
        "is_active": True,
        "full_name": f"{username} demo",
    }


def test_me_profile_contract(monkeypatch):
    monkeypatch.setattr(profiles_router, "get_user_profile", lambda username: _profile(username, False))

    client = TestClient(app)
    response = client.get("/api/v1/profiles/me", headers=_auth_header(username="sergio"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "sergio"
    assert payload["is_admin"] is False
    assert "SFTP" in payload["modules"]


def test_profile_by_username_forbidden_for_non_admin(monkeypatch):
    monkeypatch.setattr(profiles_router, "get_user_profile", lambda username: _profile(username, False))

    client = TestClient(app)
    response = client.get("/api/v1/profiles/other", headers=_auth_header(username="sergio", is_admin=False))

    assert response.status_code == 403


def test_profile_by_username_allowed_for_admin(monkeypatch):
    monkeypatch.setattr(profiles_router, "get_user_profile", lambda username: _profile(username, False))

    client = TestClient(app)
    response = client.get("/api/v1/profiles/other", headers=_auth_header(username="sergio", is_admin=True))

    assert response.status_code == 200
    assert response.json()["username"] == "other"


def test_module_access_contract(monkeypatch):
    monkeypatch.setattr(profiles_router, "can_access_module", lambda *_args, **_kwargs: True)

    client = TestClient(app)
    response = client.get("/api/v1/profiles/me/modules/SFTP", headers=_auth_header())

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["module_key"] == "SFTP"
    assert payload["has_access"] is True


def test_create_profile_forbidden_for_non_admin(monkeypatch):
    monkeypatch.setattr(profiles_router, "create_profile", lambda **_kwargs: (True, "ok"))

    client = TestClient(app)
    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(username="sergio", is_admin=False),
        json={
            "username": "new.user",
            "plain_password": "secret",
            "full_name": "Nuevo Usuario",
            "is_admin": False,
            "is_active": True,
            "modules": ["SFTP"],
        },
    )

    assert response.status_code == 403


def test_create_profile_success_for_admin(monkeypatch):
    monkeypatch.setattr(profiles_router, "create_profile", lambda **_kwargs: (True, "creado"))

    client = TestClient(app)
    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(username="admin", is_admin=True),
        json={
            "username": "new.user",
            "plain_password": "secret",
            "full_name": "Nuevo Usuario",
            "is_admin": False,
            "is_active": True,
            "modules": ["SFTP"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["username"] == "new.user"


def test_update_profile_success_for_admin(monkeypatch):
    monkeypatch.setattr(profiles_router, "update_profile", lambda **_kwargs: (True, "actualizado"))

    client = TestClient(app)
    response = client.put(
        "/api/v1/profiles/new.user",
        headers=_auth_header(username="admin", is_admin=True),
        json={
            "full_name": "Nuevo Usuario",
            "is_admin": False,
            "is_active": True,
            "modules": ["SFTP", "COBOL"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["username"] == "new.user"


def test_update_profile_forbidden_for_non_admin(monkeypatch):
    monkeypatch.setattr(profiles_router, "update_profile", lambda **_kwargs: (True, "actualizado"))

    client = TestClient(app)
    response = client.put(
        "/api/v1/profiles/new.user",
        headers=_auth_header(username="sergio", is_admin=False),
        json={
            "full_name": "Nuevo Usuario",
            "is_admin": False,
            "is_active": True,
            "modules": ["SFTP", "COBOL"],
        },
    )

    assert response.status_code == 403


def test_reset_password_success_for_admin(monkeypatch):
    monkeypatch.setattr(profiles_router, "reset_profile_password", lambda **_kwargs: (True, "password reset"))

    client = TestClient(app)
    response = client.post(
        "/api/v1/profiles/new.user/reset-password",
        headers=_auth_header(username="admin", is_admin=True),
        json={"new_password": "Nueva#2026"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["username"] == "new.user"


def test_reset_password_forbidden_for_non_admin(monkeypatch):
    monkeypatch.setattr(profiles_router, "reset_profile_password", lambda **_kwargs: (True, "password reset"))

    client = TestClient(app)
    response = client.post(
        "/api/v1/profiles/new.user/reset-password",
        headers=_auth_header(username="sergio", is_admin=False),
        json={"new_password": "Nueva#2026"},
    )

    assert response.status_code == 403
