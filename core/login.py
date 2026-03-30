import streamlit as st
import os
import time
from typing import Any, Callable
from core.utils import check_credentials, change_user_password
from core.infrastructure import backend_api_client


def _normalize_login_inputs(username: str, password: str) -> tuple[str, str]:
    """Valida credenciales ingresadas y retorna username normalizado."""
    normalized_username = (username or "").strip()
    if not normalized_username:
        raise ValueError("Debe ingresar un usuario.")
    if not password:
        raise ValueError("Debe ingresar una contraseña.")
    return normalized_username, password


def _init_auth_state() -> None:
    """Inicializa las claves de autenticación en session_state si no existen."""
    defaults = {
        "logged_in": False,
        "username": "",
        "login_error": False,
        "backend_access_token": "",
        "backend_profile": {},
        "backend_token_expires_at": 0.0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def show_login() -> None:
    """Renderiza la pantalla de login y detiene la ejecución si el usuario no está autenticado."""
    _init_auth_state()

    if st.session_state.logged_in:
        return

    # Oculta el sidebar mientras no haya sesión activa
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🏦 Scotia IA Agent Hub")
    st.subheader("Acceso al Sistema")
    st.divider()

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.container(border=True):
            st.markdown("#### Ingrese sus credenciales")
            with st.form("login_form", clear_on_submit=False):
                username_input = st.text_input("Usuario", placeholder="usuario.nombre")
                password_input = st.text_input(
                    "Contraseña", type="password", placeholder="••••••••"
                )
                submitted = st.form_submit_button(
                    "Ingresar", use_container_width=True, type="primary"
                )
                if submitted:
                    try:
                        normalized_username, normalized_password = _normalize_login_inputs(
                            username_input,
                            password_input,
                        )
                    except ValueError as exc:
                        st.session_state.login_error = True
                        st.error(f"⚠️ {exc}")
                    else:
                        authenticated = False
                        if backend_api_client.is_backend_enabled():
                            ok, _message, data = backend_api_client.login(normalized_username, normalized_password)
                            if ok:
                                st.session_state.backend_access_token = str(data.get("access_token", ""))
                                st.session_state.backend_profile = {
                                    "modules": list(data.get("modules") or []),
                                    "is_admin": bool(data.get("is_admin", False)),
                                }
                                expires_in = int(data.get("expires_in") or 0)
                                st.session_state.backend_token_expires_at = time.time() + max(expires_in, 0)
                                authenticated = True

                        if not authenticated and check_credentials(normalized_username, normalized_password):
                            st.session_state.backend_access_token = ""
                            st.session_state.backend_profile = {}
                            st.session_state.backend_token_expires_at = 0.0
                            authenticated = True

                        if authenticated:
                            st.session_state.logged_in = True
                            st.session_state.username = normalized_username
                            st.session_state.login_error = False
                            st.rerun()
                        else:
                            st.session_state.login_error = True

        if st.session_state.login_error:
            st.error("⚠️ Usuario o contraseña incorrectos. Vuelva a intentarlo.")

    st.stop()


def render_logout_button() -> None:
    """Renderiza el nombre de usuario activo y el botón de cerrar sesión en el sidebar."""
    st.caption(f"👤 {st.session_state.get('username', '')}")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def _looks_like_auth_error(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    markers = [
        "sesión inválida",
        "sesion invalida",
        "sesión expirada",
        "sesion expirada",
        "token inválido",
        "token invalido",
        "token expired",
    ]
    return any(marker in text for marker in markers)


def _auto_logout_on_backend_auth_failure_enabled() -> bool:
    raw = os.getenv("BACKEND_AUTO_LOGOUT_ON_AUTH_FAILURE", "true")
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _invalidate_backend_session(auto_logout: bool = False) -> None:
    st.session_state.backend_access_token = ""
    st.session_state.backend_profile = {}
    st.session_state.backend_token_expires_at = 0.0

    if auto_logout:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.login_error = True


def run_backend_operation_with_retry(
    operation: Callable[[str], tuple[bool, Any]],
) -> tuple[bool, Any]:
    """Ejecuta una operación backend autenticada y reintenta una vez tras refresh forzado."""
    ensure_backend_token_fresh()
    token = str(st.session_state.get("backend_access_token", "") or "")
    if not token:
        return False, "Sesión inválida o expirada. Vuelve a iniciar sesión."

    ok, payload = operation(token)
    if ok:
        return ok, payload

    message = payload if isinstance(payload, str) else str((payload or {}).get("message", ""))
    if not _looks_like_auth_error(message):
        return ok, payload

    if not ensure_backend_token_fresh(force=True):
        if _auto_logout_on_backend_auth_failure_enabled():
            _invalidate_backend_session(auto_logout=True)
        return False, "Sesión inválida o expirada. Vuelve a iniciar sesión."

    token = str(st.session_state.get("backend_access_token", "") or "")
    if not token:
        return False, "Sesión inválida o expirada. Vuelve a iniciar sesión."
    return operation(token)


def render_backend_session_status() -> None:
    """Muestra aviso cuando el backend está habilitado pero no hay sesión backend válida."""
    if not backend_api_client.is_backend_enabled():
        return

    if not st.session_state.get("logged_in", False):
        return

    has_valid_backend_session = ensure_backend_token_fresh(min_ttl_seconds=60)
    if not has_valid_backend_session:
        st.warning(
            "⚠️ Backend API activo sin token válido. Cierra sesión e inicia nuevamente para restablecer integración."
        )


def render_change_password_section() -> None:
    """Renderiza sección para cambio de contraseña del usuario autenticado."""
    username = (st.session_state.get("username", "") or "").strip()
    if not username:
        return

    with st.expander("🔐 Cambiar contraseña", expanded=False):
        with st.form("change_password_form", clear_on_submit=True):
            current_password = st.text_input("Contraseña actual", type="password")
            new_password = st.text_input("Nueva contraseña", type="password")
            confirm_password = st.text_input("Confirmar nueva contraseña", type="password")
            submitted = st.form_submit_button("Actualizar contraseña", use_container_width=True)

        if submitted:
            if (new_password or "") != (confirm_password or ""):
                st.error("⚠️ La confirmación de contraseña no coincide.")
                return

            ok = False
            message = "No fue posible actualizar la contraseña."
            if backend_api_client.is_backend_enabled():
                ok, message = run_backend_operation_with_retry(
                    lambda token: backend_api_client.change_password(token, current_password, new_password)
                )
            else:
                ok, message = change_user_password(username, current_password, new_password)
            if ok:
                st.success(f"✅ {message}")
            else:
                st.error(f"⚠️ {message}")


def ensure_backend_token_fresh(min_ttl_seconds: int = 120, force: bool = False) -> bool:
    """Renueva el token backend cuando está próximo a expirar."""
    _init_auth_state()
    if not backend_api_client.is_backend_enabled():
        return False

    token = str(st.session_state.get("backend_access_token", "") or "")
    if not token:
        return False

    expires_at = float(st.session_state.get("backend_token_expires_at", 0.0) or 0.0)
    if (not force) and (expires_at - time.time() > float(min_ttl_seconds)):
        return True

    ok, _message, data = backend_api_client.refresh_access_token(token)
    if not ok:
        _invalidate_backend_session(auto_logout=False)
        return False

    st.session_state.backend_access_token = str(data.get("access_token", ""))
    st.session_state.backend_profile = {
        "modules": list(data.get("modules") or []),
        "is_admin": bool(data.get("is_admin", False)),
    }
    expires_in = int(data.get("expires_in") or 0)
    st.session_state.backend_token_expires_at = time.time() + max(expires_in, 0)
    return bool(st.session_state.backend_access_token)
