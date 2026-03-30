import json
import os
from typing import Any
from urllib import error, request


def _as_bool(raw: str, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def is_backend_enabled() -> bool:
    enabled = _as_bool(os.getenv("BACKEND_API_ENABLED", "false"), default=False)
    return enabled and bool(get_backend_base_url())


def get_backend_base_url() -> str:
    return os.getenv("BACKEND_API_BASE_URL", "").strip().rstrip("/")


def _http_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 10.0,
) -> tuple[bool, int, dict[str, Any]]:
    base_url = get_backend_base_url()
    if not base_url:
        return False, 0, {"message": "BACKEND_API_BASE_URL no configurado."}

    url = f"{base_url}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = request.Request(url=url, data=data, headers=headers, method=method.upper())

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200))
            body = resp.read().decode("utf-8") if resp else ""
            parsed = json.loads(body) if body else {}
            return True, status, parsed if isinstance(parsed, dict) else {"data": parsed}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if hasattr(exc, "read") else ""
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"message": raw or str(exc)}
        return False, int(exc.code), parsed if isinstance(parsed, dict) else {"data": parsed}
    except Exception as exc:  # pragma: no cover
        return False, 0, {"message": f"No fue posible conectar con backend: {exc}"}


def login(username: str, password: str) -> tuple[bool, str, dict[str, Any]]:
    ok, status, body = _http_json(
        "POST",
        "/api/v1/auth/login",
        payload={"username": username, "password": password},
    )
    if ok:
        return True, body.get("message", "Autenticación exitosa."), body

    if status == 401:
        return False, "Usuario o contraseña inválidos.", body

    detail = body.get("detail")
    if isinstance(detail, str):
        return False, detail, body
    if isinstance(detail, dict):
        return False, str(detail.get("message", "Error de autenticación.")), body
    return False, str(body.get("message", "No fue posible autenticar contra backend.")), body


def change_password(token: str, current_password: str, new_password: str) -> tuple[bool, str]:
    ok, status, body = _http_json(
        "POST",
        "/api/v1/auth/change-password",
        payload={"current_password": current_password, "new_password": new_password},
        token=token,
    )
    if ok:
        return True, body.get("message", "Contraseña actualizada correctamente.")

    detail = body.get("detail")
    if isinstance(detail, str):
        return False, detail
    if isinstance(detail, dict):
        return False, str(detail.get("message", "No fue posible cambiar contraseña."))
    if status in {401, 403}:
        return False, "Sesión inválida o expirada. Vuelve a iniciar sesión."
    return False, str(body.get("message", "No fue posible cambiar contraseña en backend."))


def get_me_profile(token: str) -> tuple[bool, dict[str, Any]]:
    ok, _status, body = _http_json("GET", "/api/v1/profiles/me", token=token)
    if ok:
        return True, body
    return False, {}


def has_module_access(token: str, module_key: str) -> tuple[bool, bool]:
    ok, _status, body = _http_json("GET", f"/api/v1/profiles/me/modules/{module_key}", token=token)
    if ok:
        return True, bool(body.get("has_access", False))
    return False, False


def create_profile(
    token: str,
    username: str,
    plain_password: str,
    full_name: str,
    is_admin: bool,
    is_active: bool,
    modules: list[str],
) -> tuple[bool, str]:
    ok, status, body = _http_json(
        "POST",
        "/api/v1/profiles",
        payload={
            "username": username,
            "plain_password": plain_password,
            "full_name": full_name,
            "is_admin": bool(is_admin),
            "is_active": bool(is_active),
            "modules": list(modules or []),
        },
        token=token,
    )
    if ok:
        return True, str(body.get("message", "Usuario creado correctamente."))

    detail = body.get("detail")
    if isinstance(detail, str):
        return False, detail
    if isinstance(detail, dict):
        return False, str(detail.get("message", "No fue posible crear usuario."))
    if status in {401, 403}:
        return False, "No tienes permisos o la sesión expiró."
    return False, str(body.get("message", "No fue posible crear usuario en backend."))


def update_profile(
    token: str,
    username: str,
    full_name: str,
    is_admin: bool,
    is_active: bool,
    modules: list[str],
) -> tuple[bool, str]:
    ok, status, body = _http_json(
        "PUT",
        f"/api/v1/profiles/{username}",
        payload={
            "full_name": full_name,
            "is_admin": bool(is_admin),
            "is_active": bool(is_active),
            "modules": list(modules or []),
        },
        token=token,
    )
    if ok:
        return True, str(body.get("message", "Perfil actualizado correctamente."))

    detail = body.get("detail")
    if isinstance(detail, str):
        return False, detail
    if isinstance(detail, dict):
        return False, str(detail.get("message", "No fue posible actualizar perfil."))
    if status in {401, 403}:
        return False, "No tienes permisos o la sesión expiró."
    return False, str(body.get("message", "No fue posible actualizar perfil en backend."))


def generate_llm(token: str, system_role: str, user_content: str, model: str, temp: float) -> tuple[bool, dict[str, Any]]:
    ok, _status, body = _http_json(
        "POST",
        "/api/v1/llm/generate",
        payload={
            "system_role": system_role,
            "user_content": user_content,
            "model": model,
            "temp": temp,
        },
        token=token,
        timeout=60.0,
    )
    if ok:
        return True, body

    detail = body.get("detail")
    if isinstance(detail, dict):
        return False, {
            "success": False,
            "message": str(detail.get("message", "Error en backend LLM.")),
            "error_code": detail.get("error_code"),
            "content": None,
        }

    return False, {
        "success": False,
        "message": str(body.get("message", detail or "Error en backend LLM.")),
        "error_code": None,
        "content": None,
    }
