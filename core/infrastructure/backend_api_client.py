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


def _parse_positive_float(raw: str | None, default: float) -> float:
    try:
        value = float(str(raw).strip())
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def _workflow_timeout_seconds(step: str) -> float:
    default_timeout = _parse_positive_float(os.getenv("BACKEND_WORKFLOW_TIMEOUT_SECONDS", "60"), 60.0)
    safe_step = "".join(ch if ch.isalnum() else "_" for ch in (step or "").strip().upper())
    specific_key = f"BACKEND_WORKFLOW_TIMEOUT_{safe_step}"
    specific_raw = os.getenv(specific_key)
    if specific_raw is None:
        return default_timeout
    return _parse_positive_float(specific_raw, default_timeout)


def _http_json(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    extra_headers: dict[str, str] | None = None,
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
    if extra_headers:
        headers.update(extra_headers)

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


def refresh_access_token(token: str) -> tuple[bool, str, dict[str, Any]]:
    ok, status, body = _http_json("POST", "/api/v1/auth/refresh", token=token)
    if ok:
        return True, str(body.get("message", "Token renovado correctamente.")), body

    detail = body.get("detail")
    if isinstance(detail, str):
        return False, detail, body
    if isinstance(detail, dict):
        return False, str(detail.get("message", "No fue posible renovar sesión.")), body
    if status in {401, 403}:
        return False, "Sesión inválida o expirada. Vuelve a iniciar sesión.", body
    return False, str(body.get("message", "No fue posible renovar sesión en backend.")), body


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


def reset_profile_password(token: str, username: str, new_password: str) -> tuple[bool, str]:
    ok, status, body = _http_json(
        "POST",
        f"/api/v1/profiles/{username}/reset-password",
        payload={"new_password": new_password},
        token=token,
    )
    if ok:
        return True, str(body.get("message", "Contraseña actualizada correctamente."))

    detail = body.get("detail")
    if isinstance(detail, str):
        return False, detail
    if isinstance(detail, dict):
        return False, str(detail.get("message", "No fue posible resetear contraseña."))
    if status in {401, 403}:
        return False, "No tienes permisos o la sesión expiró."
    return False, str(body.get("message", "No fue posible resetear contraseña en backend."))


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


def execute_workflow_step(
    token: str,
    workflow: str,
    step: str,
    source_input: str,
    context: str,
    model: str,
    temp: float,
    request_id: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    workflow_key = (workflow or "").strip().lower()
    step_key = (step or "").strip().lower()

    ok, status, body = _http_json(
        "POST",
        f"/api/v1/workflows/{workflow_key}/{step_key}",
        payload={
            "input": source_input or "",
            "context": context or "",
            "model": model,
            "temp": temp,
        },
        token=token,
        extra_headers={"X-Request-ID": request_id} if request_id else None,
        timeout=_workflow_timeout_seconds(step_key),
    )
    if ok:
        return True, body

    if status in {401, 403}:
        return False, {
            "success": False,
            "message": "Sesión inválida o expirada. Vuelve a iniciar sesión.",
            "error_code": None,
            "content": None,
        }

    detail = body.get("detail")
    if isinstance(detail, dict):
        return False, {
            "success": False,
            "message": str(detail.get("message", "Error al ejecutar workflow en backend.")),
            "error_code": detail.get("error_code"),
            "content": None,
        }
    if isinstance(detail, str):
        return False, {
            "success": False,
            "message": detail,
            "error_code": None,
            "content": None,
        }

    return False, {
        "success": False,
        "message": str(body.get("message", "Error al ejecutar workflow en backend.")),
        "error_code": None,
        "content": None,
    }


def create_jira_issue(
    token: str,
    base_url: str,
    project_key: str,
    issue_type: str,
    summary: str,
    description_text: str,
    jira_user: str,
    jira_password: str,
    request_id: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    ok, status, body = _http_json(
        "POST",
        "/api/v1/integrations/jira/issue",
        payload={
            "base_url": base_url,
            "project_key": project_key,
            "issue_type": issue_type,
            "summary": summary,
            "description_text": description_text,
            "jira_user": jira_user,
            "jira_password": jira_password,
        },
        token=token,
        extra_headers={"X-Request-ID": request_id} if request_id else None,
        timeout=30.0,
    )
    if ok:
        return True, body

    detail = body.get("detail")
    if isinstance(detail, dict):
        return False, {
            "success": False,
            "message": str(detail.get("message", "No fue posible crear issue en Jira.")),
            "error_code": detail.get("error_code"),
            "data": body.get("data"),
        }
    if isinstance(detail, str):
        return False, {"success": False, "message": detail, "error_code": None, "data": None}
    if status in {401, 403}:
        return False, {
            "success": False,
            "message": "Sesión inválida o expirada. Vuelve a iniciar sesión.",
            "error_code": None,
            "data": None,
        }

    return False, {
        "success": False,
        "message": str(body.get("message", "No fue posible crear issue en Jira en backend.")),
        "error_code": None,
        "data": None,
    }


def publish_confluence_page(
    token: str,
    title: str,
    markdown_content: str,
    parent_id: str | None,
    space_key: str,
    user: str,
    api_token: str,
    request_id: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    ok, status, body = _http_json(
        "POST",
        "/api/v1/integrations/confluence/publish",
        payload={
            "title": title,
            "markdown_content": markdown_content,
            "parent_id": parent_id,
            "space_key": space_key,
            "user": user,
            "api_token": api_token,
        },
        token=token,
        extra_headers={"X-Request-ID": request_id} if request_id else None,
        timeout=30.0,
    )
    if ok:
        return True, body

    detail = body.get("detail")
    if isinstance(detail, dict):
        return False, {
            "success": False,
            "message": str(detail.get("message", "No fue posible publicar en Confluence.")),
            "error_code": detail.get("error_code"),
            "data": body.get("data"),
        }
    if isinstance(detail, str):
        return False, {"success": False, "message": detail, "error_code": None, "data": None}
    if status in {401, 403}:
        return False, {
            "success": False,
            "message": "Sesión inválida o expirada. Vuelve a iniciar sesión.",
            "error_code": None,
            "data": None,
        }

    return False, {
        "success": False,
        "message": str(body.get("message", "No fue posible publicar en Confluence en backend.")),
        "error_code": None,
        "data": None,
    }


def get_confluence_metadata(
    token: str,
    page_url: str,
    user: str,
    api_token: str,
    request_id: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    ok, status, body = _http_json(
        "POST",
        "/api/v1/integrations/confluence/metadata",
        payload={
            "page_url": page_url,
            "user": user,
            "api_token": api_token,
        },
        token=token,
        extra_headers={"X-Request-ID": request_id} if request_id else None,
        timeout=20.0,
    )
    if ok:
        return True, body

    detail = body.get("detail")
    if isinstance(detail, dict):
        return False, {
            "success": False,
            "message": str(detail.get("message", "No fue posible obtener metadata de Confluence.")),
            "error_code": detail.get("error_code"),
            "data": body.get("data"),
        }
    if isinstance(detail, str):
        return False, {"success": False, "message": detail, "error_code": None, "data": None}
    if status in {401, 403}:
        return False, {
            "success": False,
            "message": "Sesión inválida o expirada. Vuelve a iniciar sesión.",
            "error_code": None,
            "data": None,
        }

    return False, {
        "success": False,
        "message": str(body.get("message", "No fue posible obtener metadata de Confluence en backend.")),
        "error_code": None,
        "data": None,
    }
