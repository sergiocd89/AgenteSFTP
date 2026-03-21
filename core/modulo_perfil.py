import streamlit as st

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
}

# ---------------------------------------------------------------------------
# Perfiles base: módulos habilitados por usuario
# Durante la sesión, el admin puede modificarlos y se persisten en session_state
# ---------------------------------------------------------------------------
_DEFAULT_PROFILES: dict[str, list[str]] = {
    "sergio.cuevas.d": ["SFTP", "COBOL", "DTSX", "RequirementWorkflow"],
    "carlos.ramirez":  ["SFTP", "RequirementWorkflow"],
}

# Usuarios con rol administrador
_ADMINS: frozenset[str] = frozenset({"sergio.cuevas.d"})


# ---------------------------------------------------------------------------
# API interna
# ---------------------------------------------------------------------------

def _init_profiles() -> None:
    """Carga los perfiles base en session_state si aún no existen."""
    if "user_profiles" not in st.session_state:
        st.session_state.user_profiles = {
            user: list(mods) for user, mods in _DEFAULT_PROFILES.items()
        }


def get_user_modules(username: str) -> list[str]:
    """Retorna la lista de claves de módulos habilitados para el usuario."""
    _init_profiles()
    return list(st.session_state.user_profiles.get(username, []))


def has_module_access(username: str, module_key: str) -> bool:
    """Devuelve True si el usuario tiene acceso al módulo indicado."""
    return module_key in get_user_modules(username)


def is_admin(username: str) -> bool:
    """Devuelve True si el usuario tiene rol administrador."""
    return username in _ADMINS


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
