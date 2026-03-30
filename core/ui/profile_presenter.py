from collections.abc import Callable
from typing import Any


def ensure_profile_state(
    session_state: Any,
    service,
    build_meta_from_session: Callable[[], dict[str, dict[str, object]]],
) -> None:
    """Initialize profile-related state keys when absent."""
    if "user_profiles" not in session_state:
        profiles, _ = service.load_profiles_and_admins()
        session_state.user_profiles = {user: list(mods) for user, mods in profiles.items()}

    if "admin_users" not in session_state:
        _, admins = service.load_profiles_and_admins()
        session_state.admin_users = set(admins)

    if "user_profile_meta" not in session_state:
        loaded_meta = service.load_user_profile_meta()
        if loaded_meta is not None:
            session_state.user_profile_meta = loaded_meta
        else:
            session_state.user_profile_meta = build_meta_from_session()


def refresh_profile_state(
    session_state: Any,
    service,
    build_meta_from_session: Callable[[], dict[str, dict[str, object]]],
) -> None:
    """Reload profile-related state from current provider."""
    profiles, admins = service.load_profiles_and_admins()
    session_state.user_profiles = {user: list(mods) for user, mods in profiles.items()}
    session_state.admin_users = set(admins)

    loaded_meta = service.load_user_profile_meta()
    if loaded_meta is not None:
        session_state.user_profile_meta = loaded_meta
        return

    session_state.user_profile_meta = build_meta_from_session()


def apply_local_user_changes(
    session_state: Any,
    user: str,
    new_allowed: list[str],
    new_full_name: str,
    new_is_admin: bool,
    new_is_active: bool,
) -> None:
    """Apply user profile updates to in-memory session state."""
    profiles = session_state.user_profiles
    profile_meta = session_state.user_profile_meta

    profiles[user] = new_allowed
    profile_meta[user] = {
        "full_name": (new_full_name or "").strip() or user,
        "is_admin": bool(new_is_admin),
        "is_active": bool(new_is_active),
    }

    if bool(new_is_admin):
        session_state.admin_users.add(user)
    else:
        session_state.admin_users.discard(user)


def validate_create_user_inputs(
    username: str,
    plain_password: str,
    module_keys: list[str],
    valid_module_keys: set[str],
) -> tuple[bool, str, str, str, list[str]]:
    """Validate and normalize create-user form input."""
    safe_username = (username or "").strip()
    safe_password = (plain_password or "").strip()

    if not safe_username:
        return False, "Debes ingresar un username.", "", "", []
    if not safe_password:
        return False, "Debes ingresar una contraseña temporal.", "", "", []

    valid_selected_modules = [key for key in module_keys if key in valid_module_keys]
    if not valid_selected_modules:
        return False, "Debes seleccionar al menos un módulo válido.", "", "", []

    return True, "", safe_username, safe_password, valid_selected_modules


def has_profile_changes(
    current_allowed: list[str],
    current_full_name: str,
    current_is_admin: bool,
    current_is_active: bool,
    new_allowed: list[str],
    new_full_name: str,
    new_is_admin: bool,
    new_is_active: bool,
) -> tuple[bool, bool]:
    """Return (modules_changed, meta_changed) between current and edited values."""
    modules_changed = set(new_allowed) != set(current_allowed)
    meta_changed = (
        (new_full_name or "").strip() != current_full_name
        or bool(new_is_admin) != current_is_admin
        or bool(new_is_active) != current_is_active
    )
    return modules_changed, meta_changed
