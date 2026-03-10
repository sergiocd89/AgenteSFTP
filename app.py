import streamlit as st
import openai
import os
from pathlib import Path
from dotenv import load_dotenv

# --- 1. CONFIGURACIÓN E INSTANCIACIÓN ---
load_dotenv()

st.set_page_config(
    page_title="IBM i Expert Migrator v2",
    layout="wide",
    page_icon="🏗️"
)

def local_css(file_name):
    """Carga un archivo CSS local e inyecta el estilo en la app."""
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
        
local_css("assets/style.css")

@st.cache_resource
def get_openai_client():
    """Instancia el cliente de OpenAI de forma eficiente por sesión."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("🔑 API Key no configurada. Revisa tu archivo .env")
        st.stop()
    return openai.OpenAI(api_key=api_key)

def load_agent_prompt(filename: str) -> str:
    """Carga el prompt del sistema desde la carpeta de agentes."""
    path = Path(".github/agents") / filename
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Eres un asistente experto en sistemas IBM i (AS/400)."

# --- 2. LÓGICA DE IA ---
def get_ai_response(prompt, system_role):
    try:
        client = get_openai_client()
        resp = client.chat.completions.create(
            model=st.session_state.model_name,
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": prompt}
            ],
            temperature=st.session_state.temp
        )
        return resp.choices[0].message.content
    except Exception as e:
        st.error(f"❌ Error de conexión con la IA: {e}")
        return None

# --- 4. MANEJO DE ESTADO ---
state_keys = {
    "current_step": 1,
    "source_code": "",
    "analysis": "",
    "plan": "",
    "execution_code": "",
    "validation_report": "",
    "final_delivery": ""
}

for key, default_value in state_keys.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Panel de Control")
    st.session_state.model_name = st.selectbox("LLM Engine", ["gpt-4o", "gpt-4-turbo"])
    st.session_state.temp = st.slider("Precisión Técnica (0=Creatividad baja)", 0.0, 0.5, 0.0)
    st.divider()
    st.info("**Flujo de Agentes:**\n1. Carga\n2. Análisis\n3. Planificación\n4. Desarrollo\n5. Auditoría\n6. Entrega")
    if st.button("🗑️ Reiniciar Proyecto"):
        for key, val in state_keys.items(): st.session_state[key] = val
        st.rerun()

st.title("🤖 Agente Migrador de Protocolos IBM i")
st.caption("Modernización automática de FTP a SFTP mediante IA Agéntica")

# --- PASO 1: CARGA ---
st.markdown('<p class="step-header">Paso 1: Carga del Proyecto</p>', unsafe_allow_html=True)
if st.session_state.current_step == 1:
    with st.container(border=True):
        file = st.file_uploader("Sube fuentes AS/400 (RPGLE, CLP, SQLRPGLE)", type=['rpgle', 'clp', 'sqlrpgle'])
        if file and st.button("Iniciar Pipeline de Migración"):
            st.session_state.source_code = file.read().decode('utf-8')
            st.session_state.current_step = 2
            st.rerun()
elif st.session_state.source_code:
    st.success("✅ Miembro fuente cargado y listo para análisis.")

# --- PASO 2: ANÁLISIS (AGENTE 01) ---
if st.session_state.current_step >= 2:
    st.markdown('<p class="step-header">Paso 2: Análisis de Código Legacy</p>', unsafe_allow_html=True)
    if st.session_state.current_step == 2:
        with st.spinner("El Agente Analista está escaneando dependencias..."):
            sys_role = load_agent_prompt("01_analyst.md")
            st.session_state.analysis = get_ai_response(st.session_state.source_code, sys_role)
            st.session_state.current_step = 3
            st.rerun()
    st.info(st.session_state.analysis)

# --- PASO 3: PLAN DE MODIFICACIÓN (AGENTE 02) ---
if st.session_state.current_step >= 3:
    st.markdown('<p class="step-header">Paso 3: Estrategia SFTP (Arquitectura)</p>', unsafe_allow_html=True)
    if st.session_state.current_step == 3:
        with st.container(border=True):
            sys_role = load_agent_prompt("02_architect.md")
            suggested_plan = get_ai_response(st.session_state.analysis, sys_role)
            st.session_state.plan = st.text_area("Propuesta del Arquitecto:", value=suggested_plan, height=200)
            if st.button("Aprobar Plan y Generar Código"):
                st.session_state.current_step = 4
                st.rerun()
    else:
        st.success("✅ Estrategia de arquitectura validada.")

# --- PASO 4: EJECUCIÓN (AGENTE 03) ---
if st.session_state.current_step >= 4:
    st.markdown('<p class="step-header">Paso 4: Generación de Código RPGLE/CL</p>', unsafe_allow_html=True)
    if st.session_state.current_step == 4:
        with st.spinner("El Agente Desarrollador está refactorizando el código..."):
            sys_role = load_agent_prompt("03_developer.md")
            prompt = f"Código original:\n{st.session_state.source_code}\n\nPlan de Migración:\n{st.session_state.plan}"
            st.session_state.execution_code = get_ai_response(prompt, sys_role)
            st.session_state.current_step = 5
            st.rerun()
    st.code(st.session_state.execution_code, language='rpgle')

# --- PASO 5: VALIDACIÓN (AGENTE 04) ---
if st.session_state.current_step >= 5:
    st.markdown('<p class="step-header">Paso 5: Auditoría de Seguridad e Integridad</p>', unsafe_allow_html=True)
    if st.session_state.current_step == 5:
        with st.status("Auditoría en proceso...", expanded=True) as status:
            sys_role = load_agent_prompt("04_auditor.md")
            st.session_state.validation_report = get_ai_response(st.session_state.execution_code, sys_role)
            status.update(label="Auditoría completada", state="complete")
            st.session_state.current_step = 6
            st.rerun()
    st.warning(st.session_state.validation_report)

# --- PASO 6: ENTREGA ---
if st.session_state.current_step == 6:
    st.markdown('<p class="step-header">Paso 6: Paquete de Entrega Final</p>', unsafe_allow_html=True)
    with st.container(border=True):
        st.subheader("📦 Resultado de Modernización")
        st.write("El código ha sido procesado por el pipeline agéntico y está listo para pruebas en ambiente de desarrollo.")
        st.session_state.final_delivery = st.session_state.execution_code
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Descargar Fuente Modernizado (.MBR)",
                data=st.session_state.final_delivery,
                file_name="modernized_code.rpgle",
                mime="text/plain"
            )
        with col2:
            if st.button("🚀 Iniciar Nueva Migración"):
                for key, val in state_keys.items(): st.session_state[key] = val
                st.rerun()