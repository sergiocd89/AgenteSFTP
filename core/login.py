import streamlit as st
from core.utils import check_credentials


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
                        if check_credentials(normalized_username, normalized_password):
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
