import streamlit as st
from utils import apply_custom_theme, get_openai_client
# Importamos las funciones principales de tus módulos
from modulo_sftp import show_sftp_migration
from modulo_cobol import show_cobol_migration
from modulo_dtsx import show_dtsx_generation

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Scotia IA Agent Hub",
    layout="wide",
    page_icon="🏦"
)

# --- 2. INICIALIZACIÓN DE ESTADO GLOBAL ---
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

    st.info("AS/400 Legacy Agent Migrator v2.0")

# --- 4. LÓGICA DE NAVEGACIÓN (PORTAL VS MÓDULOS) ---

if st.session_state.app_mode == "Portal":
    # --- PÁGINA DE INICIO ---
    st.title("🏦 Scotia IA Agent Hub")
    st.subheader("Seleccione el flujo de modernización que desea ejecutar:")
    st.write("Herramientas agénticas especializadas en sistemas legacy.")
    
    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        with st.container(border=True):
            st.markdown("### 🔐 Módulo FTP ➔ SFTP")
            st.write("""
            **Objetivo:** Migración automática de comandos de transferencia inseguros.
            - Analiza fuentes RPGLE y CL.
            - Implementa protocolos SSH/SFTP.
            - Genera auditoría de seguridad.
            """)
            if st.button("Iniciar Migración SFTP", use_container_width=True, type="primary"):
                st.session_state.app_mode = "SFTP_Module"
                st.rerun()

    with col2:
        with st.container(border=True):
            st.markdown("### 🐍 Módulo COBOL ➔ Python")
            st.write("""
            **Objetivo:** Transposición de lógica de negocio legacy a Python moderno.
            - Identifica párrafos y dependencias COBOL.
            - Crea estructura de microservicios.
            - Genera documentación técnica automática.
            """)
            if st.button("Iniciar Migración COBOL", use_container_width=True, type="primary"):
                st.session_state.app_mode = "COBOL_Module"
                st.rerun()

    with col3:
        with st.container(border=True):
            st.markdown("### 📦 Módulo COBOL ➔ DTSX")
            st.write("""
            **Objetivo:** Generación asistida de paquetes SSIS a partir de COBOL con SQL Server y Sybase.
            - Detecta bloques `EXEC SQL` y cadenas de conexión.
            - Propone connection managers y control flow.
            - Entrega un paquete `.dtsx` descargable.
            """)
            if st.button("Generar Paquete DTSX", use_container_width=True, type="primary"):
                st.session_state.app_mode = "DTSX_Module"
                st.rerun()

    st.divider()
    st.caption("Ecosistema diseñado para arquitectos de sistemas IBM i.")

elif st.session_state.app_mode == "SFTP_Module":
    # Llamada al módulo de SFTP
    show_sftp_migration()

elif st.session_state.app_mode == "COBOL_Module":
    # Llamada al módulo de COBOL
    show_cobol_migration()

elif st.session_state.app_mode == "DTSX_Module":
    # Llamada al módulo de COBOL a DTSX
    show_dtsx_generation()