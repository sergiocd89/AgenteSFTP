from fastapi.testclient import TestClient

from AgenteSFTPBackend.app.main import app
from AgenteSFTPBackend.app.security import create_access_token
from AgenteSFTPBackend.app.routers import auth as auth_router


def _auth_header(username: str = "sergio", modules: list[str] | None = None, is_admin: bool = False) -> dict[str, str]:
    token, _ = create_access_token(username, modules or ["SFTP"], is_admin)
    return {"Authorization": f"Bearer {token}"}


def test_login_success_returns_token_and_profile(monkeypatch):
    monkeypatch.setattr(auth_router, "authenticate_user", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        auth_router,
        "get_user_profile",
        lambda username: {
            "username": username,
            "modules": ["SFTP", "COBOL"],
            "is_admin": True,
            "is_active": True,
            "full_name": "Usuario Demo",
        },
    )

    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"username": "sergio", "password": "demo"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"
    assert payload["modules"] == ["SFTP", "COBOL"]
    assert payload["is_admin"] is True


def test_login_invalid_credentials_returns_401(monkeypatch):
    monkeypatch.setattr(auth_router, "authenticate_user", lambda *_args, **_kwargs: False)

    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"username": "sergio", "password": "bad"})

    assert response.status_code == 401
    assert "inválidos" in response.json()["detail"]


def test_change_password_success(monkeypatch):
    monkeypatch.setattr(auth_router, "change_user_password", lambda **_kwargs: (True, "ok"))

    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/change-password",
        headers=_auth_header(),
        json={"current_password": "old", "new_password": "new"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_change_password_validation_error(monkeypatch):
    monkeypatch.setattr(auth_router, "change_user_password", lambda **_kwargs: (False, "nope"))

    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/change-password",
        headers=_auth_header(),
        json={"current_password": "old", "new_password": "new"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "nope"


def test_refresh_success_returns_new_token():
    client = TestClient(app)
    response = client.post("/api/v1/auth/refresh", headers=_auth_header(modules=["SFTP", "DTSX"], is_admin=True))

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["access_token"]
    assert payload["modules"] == ["SFTP", "DTSX"]
    assert payload["is_admin"] is True
