import streamlit as st
import os
from core.domain.profile_service import ProfileService
from core.infrastructure import auth_db
from core.infrastructure import backend_api_client
from core.ui.profile_presenter import (
    ensure_profile_state,
    refresh_profile_state,
    apply_local_user_changes,
    validate_create_user_inputs,
    has_profile_changes,
)

try:
    import psycopg
except ImportError:  # pragma: no cover - depende del entorno
    psycopg = None

try:
    import pyodbc
except ImportError:  # pragma: no cover - depende del entorno
    pyodbc = None

# ---------------------------------------------------------------------------
# Catálogo de módulos disponibles en la aplicación
# Clave → metadatos de presentación y navegación
# ---------------------------------------------------------------------------
MODULES: dict[str, dict] = {
    "SFTP": {
        "label":    "🔐 FTP ➔ SFTP",
        "app_mode": "SFTP_Module",
    },
    "COBOL": {
        "label":    "🐍 COBOL ➔ Python",
        "app_mode": "COBOL_Module",
    },
    "DTSX": {
        "label":    "📦 COBOL ➔ DTSX",
        "app_mode": "DTSX_Module",
    },
    "RequirementWorkflow": {
        "label":    "🧩 Requirement Workflow",
        "app_mode": "Requirement_Workflow_Module",
    },
    "Documentation": {
        "label":    "📝 Documentación",
        "app_mode": "Documentation_Module",
    },
}


# ---------------------------------------------------------------------------
# API interna
# ---------------------------------------------------------------------------

def _init_profiles() -> None:
    """Carga perfiles y admins en session_state si aún no existen."""
    ensure_profile_state(st.session_state, _build_profile_service(), _build_meta_from_session)


def _build_meta_from_session() -> dict[str, dict[str, object]]:
    """Construye metadata base de usuarios desde la sesión activa."""
    profiles: dict[str, list[str]] = st.session_state.get("user_profiles", {})
    admins: set[str] = st.session_state.get("admin_users", set())

    return {
        username: {
            "full_name": username,
            "is_admin": username in admins,
            "is_active": True,
        }
        for username in profiles
    }


def _get_auth_provider() -> str:
    """Retorna proveedor de autenticación y datos configurado globalmente."""
    return auth_db.get_auth_provider()


def _build_profile_service() -> ProfileService:
    """Build profile domain service with infrastructure dependencies."""
    return ProfileService(
        provider=_get_auth_provider(),
        database_url=auth_db.get_database_url(),
        sqlserver_conn_str=_build_sqlserver_conn_str(),
        psycopg_module=psycopg,
        pyodbc_module=pyodbc,
        modules=MODULES,
        env_user_profiles_json=os.getenv("USER_PROFILES_JSON", ""),
        env_admins_csv=os.getenv("ADMINS_CSV", ""),
    )


def _build_sqlserver_conn_str() -> str:
    """Construye string de conexión ODBC para SQL Server."""
    return auth_db.build_sqlserver_conn_str()


def _load_profiles_and_admins() -> tuple[dict[str, list[str]], set[str]]:
    """Resuelve perfiles/admins desde DB o env según proveedor."""
    return _build_profile_service().load_profiles_and_admins()


def _refresh_profiles_from_provider() -> None:
    """Recarga perfiles/admins/meta desde el proveedor activo."""
    refresh_profile_state(st.session_state, _build_profile_service(), _build_meta_from_session)


def create_user_profile(
    username: str,
    plain_password: str,
    full_name: str,
    is_admin_user: bool,
    is_active_user: bool,
    module_keys: list[str],
    actor: str,
) -> tuple[bool, str]:
    """Crea un usuario nuevo y sus permisos usando el proveedor activo."""
    ok_inputs, msg_inputs, safe_username, safe_password, valid_module_keys = validate_create_user_inputs(
        username,
        plain_password,
        module_keys,
        set(MODULES.keys()),
    )
    if not ok_inputs:
        return False, msg_inputs

    token = str(st.session_state.get("backend_access_token", "") or "")
    if backend_api_client.is_backend_enabled() and token:
        return backend_api_client.create_profile(
            token=token,
            username=safe_username,
            plain_password=safe_password,
            full_name=full_name,
            is_admin=bool(is_admin_user),
            is_active=bool(is_active_user),
            modules=valid_module_keys,
        )

    provider = _get_auth_provider()
    service = _build_profile_service()
    if provider in {"postgres", "postgresql", "db", "sqlserver", "mssql"}:
        ok, msg = service.create_user_profile(
            safe_username,
            safe_password,
            full_name,
            is_admin_user,
            is_active_user,
            valid_module_keys,
            actor,
        )
        if not ok:
            return ok, msg

        _refresh_profiles_from_provider()
        return ok, msg

    if provider not in {"env", ""}:
        return False, f"AUTH_PROVIDER no soportado para perfiles: {provider}."

    _init_profiles()
    profiles: dict[str, list[str]] = st.session_state.user_profiles
    if safe_username in profiles:
        return False, f"El usuario {safe_username} ya existe en la sesión activa."

    apply_local_user_changes(
        st.session_state,
        safe_username,
        valid_module_keys,
        full_name,
        is_admin_user,
        is_active_user,
    )

    return True, f"Usuario {safe_username} creado en sesión activa (modo env)."


def _load_profiles_and_admins_from_env() -> tuple[dict[str, list[str]], set[str]]:
    """Carga perfiles/admins desde variables de entorno."""
    return _build_profile_service().load_profiles_and_admins_from_env()


def get_user_modules(username: str) -> list[str]:
    """Retorna la lista de claves de módulos habilitados para el usuario."""
    current_username = str(st.session_state.get("username", "") or "")
    token = str(st.session_state.get("backend_access_token", "") or "")
    if (
        backend_api_client.is_backend_enabled()
        and token
        and current_username
        and current_username == (username or "")
    ):
        ok, profile = backend_api_client.get_me_profile(token)
        if ok:
            modules = list(profile.get("modules") or [])
            st.session_state.backend_profile = {
                "modules": modules,
                "is_admin": bool(profile.get("is_admin", False)),
            }
            return modules

    _init_profiles()
    return list(st.session_state.user_profiles.get(username, []))


def has_module_access(username: str, module_key: str) -> bool:
    """Devuelve True si el usuario tiene acceso al módulo indicado."""
    if module_key not in MODULES:
        raise ValueError(f"module_key no soportado: {module_key}")

    current_username = str(st.session_state.get("username", "") or "")
    token = str(st.session_state.get("backend_access_token", "") or "")
    if (
        backend_api_client.is_backend_enabled()
        and token
        and current_username
        and current_username == (username or "")
    ):
        ok, allowed = backend_api_client.has_module_access(token, module_key)
        if ok:
            return allowed

    return module_key in get_user_modules(username)


def is_admin(username: str) -> bool:
    """Devuelve True si el usuario tiene rol administrador."""
    current_username = str(st.session_state.get("username", "") or "")
    token = str(st.session_state.get("backend_access_token", "") or "")
    if (
        backend_api_client.is_backend_enabled()
        and token
        and current_username
        and current_username == (username or "")
    ):
        ok, profile = backend_api_client.get_me_profile(token)
        if ok:
            is_admin_value = bool(profile.get("is_admin", False))
            st.session_state.backend_profile = {
                "modules": list(profile.get("modules") or []),
                "is_admin": is_admin_value,
            }
            return is_admin_value

    _init_profiles()
    return username in st.session_state.admin_users


# ---------------------------------------------------------------------------
# Panel de administración de perfiles
# ---------------------------------------------------------------------------

def show_profile_admin() -> None:
    """Renderiza el panel de gestión de perfiles (solo para administradores)."""
    username = st.session_state.get("username", "")
    if not is_admin(username):
        st.error("🚫 No tienes permisos para acceder a esta sección.")
        return

    _init_profiles()

    st.title("👥 Administración de Perfiles")
    st.caption("Define qué módulos puede ver y usar cada usuario. Los cambios son efectivos de inmediato para la sesión activa.")
    st.divider()

    profiles: dict[str, list[str]] = st.session_state.user_profiles
    profile_meta: dict[str, dict[str, object]] = st.session_state.user_profile_meta
    module_keys = list(MODULES.keys())
    provider = _get_auth_provider()
    service = _build_profile_service()
    token = str(st.session_state.get("backend_access_token", "") or "")
    use_backend = backend_api_client.is_backend_enabled() and bool(token)

    with st.expander("➕ Crear nuevo usuario", expanded=False):
        with st.form("create_user_profile_form"):
            col_u, col_n = st.columns([1, 1])
            with col_u:
                new_username = st.text_input(
                    "Username",
                    placeholder="nombre.apellido",
                )
            with col_n:
                new_full_name = st.text_input(
                    "Nombre completo",
                    placeholder="Nombre Apellido",
                )

            col_p, col_a, col_s = st.columns([1, 1, 1])
            with col_p:
                new_password = st.text_input(
                    "Contraseña temporal",
                    type="password",
                )
            with col_a:
                new_is_admin = st.checkbox("Es administrador", value=False)
            with col_s:
                new_is_active = st.checkbox("Activo", value=True)

            new_modules = st.multiselect(
                "Módulos habilitados",
                options=module_keys,
                default=[],
            )

            create_submitted = st.form_submit_button(
                "Crear usuario",
                type="primary",
                use_container_width=True,
            )

        if create_submitted:
            actor = st.session_state.get("username", "system")
            ok, message = create_user_profile(
                username=new_username,
                plain_password=new_password,
                full_name=new_full_name,
                is_admin_user=new_is_admin,
                is_active_user=new_is_active,
                module_keys=new_modules,
                actor=actor,
            )
            if ok:
                st.success(message)
                if use_backend:
                    _refresh_profiles_from_provider()
                st.rerun()
            else:
                st.error(message)

    changed = False
    for user, allowed in profiles.items():
        user_meta = profile_meta.get(
            user,
            {
                "full_name": user,
                "is_admin": user in st.session_state.admin_users,
                "is_active": True,
            },
        )
        current_full_name = str(user_meta.get("full_name", user)) or user
        current_is_admin = bool(user_meta.get("is_admin", user in st.session_state.admin_users))
        current_is_active = bool(user_meta.get("is_active", True))

        with st.container(border=True):
            col_title, col_name, col_admin, col_active, col_pwd, col_pwd_btn, *col_checks = st.columns(
                [1.4, 2.0, 1, 1, 1.4, 1.1] + [1] * len(module_keys)
            )
            with col_title:
                st.markdown(f"**👤 {user}**")
            with col_name:
                new_full_name = st.text_input(
                    "Nombre",
                    value=current_full_name,
                    key=f"profile_meta_full_name_{user}",
                )
            with col_admin:
                new_is_admin = st.checkbox(
                    "Admin",
                    value=current_is_admin,
                    key=f"profile_meta_is_admin_{user}",
                )
            with col_active:
                new_is_active = st.checkbox(
                    "Activo",
                    value=current_is_active,
                    key=f"profile_meta_is_active_{user}",
                )
            with col_pwd:
                reset_password_value = st.text_input(
                    "Nueva contraseña",
                    value="",
                    type="password",
                    key=f"profile_reset_password_{user}",
                )
            with col_pwd_btn:
                do_reset_password = st.button(
                    "Reset Pass",
                    key=f"profile_reset_btn_{user}",
                    use_container_width=True,
                )

            new_allowed: list[str] = []
            for idx, key in enumerate(module_keys):
                with col_checks[idx]:
                    checked = st.checkbox(
                        MODULES[key]["label"],
                        value=key in allowed,
                        key=f"profile_{user}_{key}",
                    )
                    if checked:
                        new_allowed.append(key)

            if do_reset_password:
                if use_backend:
                    ok_reset, msg_reset = backend_api_client.reset_profile_password(
                        token=token,
                        username=user,
                        new_password=reset_password_value,
                    )
                    if ok_reset:
                        st.success(msg_reset)
                    else:
                        st.error(msg_reset)
                elif provider in {"postgres", "postgresql", "db", "sqlserver", "mssql"}:
                    actor = st.session_state.get("username", "system")
                    ok_reset, msg_reset = service.admin_reset_password(user, reset_password_value, actor)
                    if ok_reset:
                        st.success(msg_reset)
                    else:
                        st.error(msg_reset)
                elif provider in {"env", ""}:
                    st.info("El reseteo de contraseña solo está disponible con AUTH_PROVIDER=postgres o AUTH_PROVIDER=sqlserver.")
                else:
                    st.error(f"AUTH_PROVIDER no soportado: {provider}.")

            modules_changed, meta_changed = has_profile_changes(
                allowed,
                current_full_name,
                current_is_admin,
                current_is_active,
                new_allowed,
                new_full_name,
                bool(new_is_admin),
                bool(new_is_active),
            )

            if modules_changed or meta_changed:
                if use_backend:
                    ok_upd, msg_upd = backend_api_client.update_profile(
                        token=token,
                        username=user,
                        full_name=(new_full_name or "").strip(),
                        is_admin=bool(new_is_admin),
                        is_active=bool(new_is_active),
                        modules=new_allowed,
                    )
                    if ok_upd:
                        apply_local_user_changes(
                            st.session_state,
                            user,
                            new_allowed,
                            new_full_name,
                            bool(new_is_admin),
                            bool(new_is_active),
                        )
                        changed = True
                    else:
                        st.error(msg_upd)
                elif provider in {"postgres", "postgresql", "db", "sqlserver", "mssql"}:
                    actor = st.session_state.get("username", "system")
                    if service.update_user_profile(
                        username=user,
                        full_name=(new_full_name or "").strip(),
                        is_admin_user=bool(new_is_admin),
                        is_active_user=bool(new_is_active),
                        module_keys=new_allowed,
                        actor=actor,
                    ):
                        apply_local_user_changes(
                            st.session_state,
                            user,
                            new_allowed,
                            new_full_name,
                            bool(new_is_admin),
                            bool(new_is_active),
                        )
                        changed = True
                    else:
                        st.error(f"No fue posible guardar perfil de {user} en base de datos.")
                elif provider in {"env", ""}:
                    apply_local_user_changes(
                        st.session_state,
                        user,
                        new_allowed,
                        new_full_name,
                        bool(new_is_admin),
                        bool(new_is_active),
                    )
                    changed = True
                else:
                    st.error(f"AUTH_PROVIDER no soportado: {provider}.")

    st.divider()
    if changed:
        st.success("✅ Cambios guardados en la sesión activa.")
    else:
        st.info("ℹ️ Sin cambios pendientes.")
