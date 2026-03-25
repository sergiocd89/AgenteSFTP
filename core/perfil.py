import streamlit as st
import json
import os

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
# Perfiles base: se usan como fallback si no hay configuración externa.
# ---------------------------------------------------------------------------
_FALLBACK_PROFILES: dict[str, list[str]] = {
    "sergio.cuevas.d": ["SFTP", "COBOL", "DTSX", "RequirementWorkflow", "Documentation"],
    "carlos.ramirez":  ["SFTP", "RequirementWorkflow", "Documentation"],
}

_FALLBACK_ADMINS: frozenset[str] = frozenset({"sergio.cuevas.d"})


# ---------------------------------------------------------------------------
# API interna
# ---------------------------------------------------------------------------

def _init_profiles() -> None:
    """Carga perfiles y admins en session_state si aún no existen."""
    if "user_profiles" not in st.session_state:
        profiles, _ = _load_profiles_and_admins_from_env()
        st.session_state.user_profiles = {
            user: list(mods) for user, mods in profiles.items()
        }

    if "admin_users" not in st.session_state:
        _, admins = _load_profiles_and_admins_from_env()
        st.session_state.admin_users = set(admins)


def _load_profiles_and_admins_from_env() -> tuple[dict[str, list[str]], set[str]]:
    """Carga perfiles/admins desde variables de entorno con fallback seguro."""
    raw_profiles = os.getenv("USER_PROFILES_JSON", "").strip()
    profiles: dict[str, list[str]] = {}

    if raw_profiles:
        try:
            parsed = json.loads(raw_profiles)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, dict):
            valid_module_keys = set(MODULES.keys())
            for username, modules in parsed.items():
                safe_username = str(username).strip()
                if not safe_username or not isinstance(modules, list):
                    continue

                filtered = [
                    str(module_key)
                    for module_key in modules
                    if str(module_key) in valid_module_keys
                ]
                if filtered:
                    profiles[safe_username] = filtered

    if not profiles:
        profiles = {user: list(mods) for user, mods in _FALLBACK_PROFILES.items()}

    raw_admins = os.getenv("ADMINS_CSV", "").strip()
    if raw_admins:
        admins = {
            admin.strip()
            for admin in raw_admins.split(",")
            if admin.strip() in profiles
        }
    else:
        admins = {admin for admin in _FALLBACK_ADMINS if admin in profiles}

    # Garantiza al menos un admin para no bloquear gestión de perfiles.
    if not admins and profiles:
        first_user = next(iter(profiles.keys()))
        admins = {first_user}

    return profiles, admins


def get_user_modules(username: str) -> list[str]:
    """Retorna la lista de claves de módulos habilitados para el usuario."""
    _init_profiles()
    return list(st.session_state.user_profiles.get(username, []))


def has_module_access(username: str, module_key: str) -> bool:
    """Devuelve True si el usuario tiene acceso al módulo indicado."""
    if module_key not in MODULES:
        raise ValueError(f"module_key no soportado: {module_key}")
    return module_key in get_user_modules(username)


def is_admin(username: str) -> bool:
    """Devuelve True si el usuario tiene rol administrador."""
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
    module_keys = list(MODULES.keys())

    changed = False
    for user, allowed in profiles.items():
        with st.container(border=True):
            col_title, *col_checks = st.columns([1.4] + [1] * len(module_keys))
            with col_title:
                st.markdown(f"**👤 {user}**")

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

            if set(new_allowed) != set(allowed):
                profiles[user] = new_allowed
                changed = True

    st.divider()
    if changed:
        st.success("✅ Cambios guardados en la sesión activa.")
    else:
        st.info("ℹ️ Sin cambios pendientes.")
