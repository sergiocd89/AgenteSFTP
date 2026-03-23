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
from modules.modulo_documentation import show_documentation_module

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
        "search_text": "ftp sftp ibm i as400 rpgle cl ssh seguridad qsh strqsh",
        "tags": ["ftp", "sftp", "ibm i", "as400", "rpgle", "cl", "seguridad"],
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
        "search_text": "cobol python migracion microservicios refactor legacy",
        "tags": ["cobol", "python", "legacy", "microservicios", "migracion"],
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
        "search_text": "cobol dtsx ssis sql server sybase etl paquete",
        "tags": ["cobol", "dtsx", "ssis", "sql server", "sybase", "etl"],
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
        "search_text": "requirement workflow historia de usuario mermaid sizing qa issue jira github",
        "tags": ["requirements", "workflow", "user story", "mermaid", "qa", "jira"],
        "body": (
            "**Objetivo:** Transformar un requerimiento en un ticket técnico listo para ejecución.\n"
            "- Ingreso de requerimiento mediante cuadro de texto.\n"
            "- Carga de documentos de contexto (multiarchivo).\n"
            "- Pipeline completo de agentes: creación, refinamiento, diagrama, sizing, QA e issue final."
        ),
        "button":   "Iniciar Requirement Workflow",
        "app_mode": "Requirement_Workflow_Module",
    },
    "Documentation": {
        "title":    "### 📝 Módulo Documentación de Archivos o Paquetes",
        "search_text": "documentacion analisis archivos paquete zip as400 rpgle cobol java asp visual basic jsf react confluence",
        "tags": ["documentacion", "analisis", "archivo", "paquete", "confluence", "as400", "rpgle", "cobol", "java", "asp", "visual basic", "jsf", "react"],
        "body": (
            "**Objetivo:** Generar documentación técnica automática desde archivos o paquetes subidos.\n"
            "- Selecciona tecnologías objetivo (AS400, RPG, Cobol, Java, ASP, Visual Basic, JSF, React).\n"
            "- Analiza archivo único o paquete `.zip`.\n"
            "- Entrega documentación descargable y opción de publicación en Confluence."
        ),
        "button":   "Iniciar Módulo Documentación",
        "app_mode": "Documentation_Module",
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
    allowed_cards = [k for k in _MODULE_CARDS if k in allowed_modules]

    # Buscador principal por texto y tags para filtrar módulos según necesidad.
    available_tags = sorted({
        tag
        for key in allowed_cards
        for tag in _MODULE_CARDS[key].get("tags", [])
    })

    search_query = st.text_input(
        "🔎 Buscar módulo por texto",
        placeholder="Ejemplo: COBOL, SFTP, seguridad, ETL, QA...",
    ).strip().lower()

    selected_tags = st.multiselect(
        "Filtrar por tags",
        options=available_tags,
        help="Si seleccionas varios tags, se mostrarán módulos que contengan todos esos tags.",
    )

    selected_tags_normalized = {tag.lower() for tag in selected_tags}

    visible_cards = []
    for key in allowed_cards:
        card = _MODULE_CARDS[key]
        card_tags = {tag.lower() for tag in card.get("tags", [])}
        searchable_text = " ".join([
            key,
            card.get("title", ""),
            card.get("body", ""),
            card.get("search_text", ""),
            " ".join(card.get("tags", [])),
        ]).lower()

        if search_query and search_query not in searchable_text:
            continue

        if selected_tags_normalized and not selected_tags_normalized.issubset(card_tags):
            continue

        visible_cards.append(key)

    if search_query or selected_tags:
        st.caption(f"Resultados: {len(visible_cards)} módulo(s)")

    if not visible_cards:
        if allowed_cards:
            st.warning("No se encontraron módulos que coincidan con la búsqueda actual.")
        else:
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
                        st.caption("TAGS: " + ", ".join(card.get("tags", [])))
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

elif st.session_state.app_mode == "Documentation_Module":
    if has_module_access(_current_user, "Documentation"):
        show_documentation_module()
    else:
        st.error("🚫 No tienes acceso al módulo Documentación.")
        st.session_state.app_mode = "Portal"
        st.rerun()