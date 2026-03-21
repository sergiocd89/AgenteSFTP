import streamlit as st
from core.utils import apply_custom_theme, get_openai_client
from core.modulo_login import show_login, render_logout_button
from core.modulo_perfil import (
    get_user_modules,
    has_module_access,
    is_admin,
    show_profile_admin,
    MODULES,
)
# Importamos las funciones principales de tus módulos
from modules.modulo_sftp import show_sftp_migration
from modules.modulo_cobol import show_cobol_migration
from modules.modulo_dtsx import show_dtsx_generation
from modules.modulo_Requirement_WorkFlow import show_requirement_workflow

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Scotia IA Agent Hub",
    layout="wide",
    page_icon="🏦"
)

# --- 2. AUTENTICACIÓN ---
show_login()

# --- 3. INICIALIZACIÓN DE ESTADO GLOBAL ---
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "Portal"

# Parámetros compartidos para la IA
if "model_name" not in st.session_state:
    st.session_state.model_name = "gpt-4o"
if "temp" not in st.session_state:
    st.session_state.temp = 0.0

# --- 3. SIDEBAR GLOBAL ---
with st.sidebar:
    st.title("⚙️ Configuración Global")
    render_logout_button()

    st.divider()

    # Selector de Tema
    theme = st.selectbox("Apariencia", ["Dark Mode", "Light Mode"], index=0)
    apply_custom_theme(theme)
    
    st.divider()
    
    # Configuración del LLM (Afecta a todos los módulos)
    st.session_state.model_name = st.selectbox(
        "LLM Engine", 
        ["gpt-4o", "gpt-4-turbo"],
        help="Selecciona el modelo de IA para la refactorización."
    )
    st.session_state.temp = st.slider(
        "Precisión Técnica (Temp)", 
        0.0, 0.5, 0.0, 0.05,
        help="0.0 es más preciso, valores altos son más creativos."
    )
    
    st.divider()
    
    # Botón para volver al inicio siempre visible
    if st.session_state.app_mode != "Portal":
        if st.button("⬅️ Volver al Menú Principal", use_container_width=True):
            st.session_state.app_mode = "Portal"
            st.rerun()

    # Panel de administración de perfiles (solo para admins)
    if is_admin(st.session_state.get("username", "")):
        st.divider()
        if st.button("👥 Administrar Perfiles", use_container_width=True):
            st.session_state.app_mode = "Profile_Admin"
            st.rerun()

    st.info("AS/400 Legacy Agent Migrator v2.0")

# --- 4. LÓGICA DE NAVEGACIÓN (PORTAL VS MÓDULOS) ---

_MODULE_CARDS: dict[str, dict] = {
    "SFTP": {
        "title":    "### 🔐 Módulo FTP ➔ SFTP",
        "body": (
            "**Objetivo:** Migración automática de comandos de transferencia inseguros.\n"
            "- Analiza fuentes RPGLE y CL.\n"
            "- Implementa protocolos SSH/SFTP.\n"
            "- Genera auditoría de seguridad."
        ),
        "button":   "Iniciar Migración SFTP",
        "app_mode": "SFTP_Module",
    },
    "COBOL": {
        "title":    "### 🐍 Módulo COBOL ➔ Python",
        "body": (
            "**Objetivo:** Transposición de lógica de negocio legacy a Python moderno.\n"
            "- Identifica párrafos y dependencias COBOL.\n"
            "- Crea estructura de microservicios.\n"
            "- Genera documentación técnica automática."
        ),
        "button":   "Iniciar Migración COBOL",
        "app_mode": "COBOL_Module",
    },
    "DTSX": {
        "title":    "### 📦 Módulo COBOL ➔ DTSX",
        "body": (
            "**Objetivo:** Generación asistida de paquetes SSIS a partir de COBOL con SQL Server y Sybase.\n"
            "- Detecta bloques `EXEC SQL` y cadenas de conexión.\n"
            "- Propone connection managers y control flow.\n"
            "- Entrega un paquete `.dtsx` descargable."
        ),
        "button":   "Generar Paquete DTSX",
        "app_mode": "DTSX_Module",
    },
    "RequirementWorkflow": {
        "title":    "### 🧩 Módulo Requirement Workflow",
        "body": (
            "**Objetivo:** Transformar un requerimiento en un ticket técnico listo para ejecución.\n"
            "- Ingreso de requerimiento mediante cuadro de texto.\n"
            "- Carga de documentos de contexto (multiarchivo).\n"
            "- Pipeline completo de agentes: creación, refinamiento, diagrama, sizing, QA e issue final."
        ),
        "button":   "Iniciar Requirement Workflow",
        "app_mode": "Requirement_Workflow_Module",
    },
}

_current_user = st.session_state.get("username", "")

if st.session_state.app_mode == "Portal":
    # --- PÁGINA DE INICIO ---
    st.title("🏦 Scotia IA Agent Hub")
    st.subheader("Seleccione el flujo de modernización que desea ejecutar:")
    st.write("Herramientas agénticas especializadas en sistemas legacy.")
    st.divider()

    allowed_modules = get_user_modules(_current_user)
    visible_cards = [k for k in _MODULE_CARDS if k in allowed_modules]

    if not visible_cards:
        st.warning("🚫 No tienes acceso a ningún módulo. Contacta al administrador.")
    else:
        for row_start in range(0, len(visible_cards), 2):
            row_keys = visible_cards[row_start:row_start + 2]
            cols = st.columns(len(row_keys))
            for col, key in zip(cols, row_keys):
                card = _MODULE_CARDS[key]
                with col:
                    with st.container(border=True):
                        st.markdown(card["title"])
                        st.write(card["body"])
                        if st.button(card["button"], use_container_width=True, type="primary", key=f"portal_btn_{key}"):
                            st.session_state.app_mode = card["app_mode"]
                            st.rerun()

    st.divider()
    st.caption("Ecosistema diseñado para arquitectos de sistemas IBM i.")

elif st.session_state.app_mode == "Profile_Admin":
    show_profile_admin()

elif st.session_state.app_mode == "SFTP_Module":
    if has_module_access(_current_user, "SFTP"):
        show_sftp_migration()
    else:
        st.error("🚫 No tienes acceso al módulo FTP ➔ SFTP.")
        st.session_state.app_mode = "Portal"
        st.rerun()

elif st.session_state.app_mode == "COBOL_Module":
    if has_module_access(_current_user, "COBOL"):
        show_cobol_migration()
    else:
        st.error("🚫 No tienes acceso al módulo COBOL ➔ Python.")
        st.session_state.app_mode = "Portal"
        st.rerun()

elif st.session_state.app_mode == "DTSX_Module":
    if has_module_access(_current_user, "DTSX"):
        show_dtsx_generation()
    else:
        st.error("🚫 No tienes acceso al módulo COBOL ➔ DTSX.")
        st.session_state.app_mode = "Portal"
        st.rerun()

elif st.session_state.app_mode == "Requirement_Workflow_Module":
    if has_module_access(_current_user, "RequirementWorkflow"):
        show_requirement_workflow()
    else:
        st.error("🚫 No tienes acceso al módulo Requirement Workflow.")
        st.session_state.app_mode = "Portal"
        st.rerun()