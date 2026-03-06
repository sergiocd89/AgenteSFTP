import streamlit as st
import openai
import os
from dotenv import load_dotenv

# 1. Configuración de Entorno y Seguridad
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=api_key) if api_key else None

st.set_page_config(page_title="Expert Migration Agent", layout="wide")
st.title("🤖 Agente de Migración Crítica (AS/400)")

# Inicializar estados si no existen
if "step" not in st.session_state:
    st.session_state.step = "upload"
if "plan" not in st.session_state:
    st.session_state.plan = ""
if "source_code" not in st.session_state:
    st.session_state.source_code = ""

# 2. Barra Lateral - Configuración Técnica
with st.sidebar:
    st.header("⚙️ Configuración")
    model_name = st.selectbox("Modelo", ["gpt-4o", "gpt-4-turbo"])
    max_retries = st.slider("Reintentos Autocuración", 1, 5, 3)
    if api_key:
        st.success("✅ API Key cargada de .env")
    else:
        st.error("❌ Falta OPENAI_API_KEY en .env")

# 3. Prompts de Especialidad
SYSTEM_PROMPT_PLANNER = """Actúa como Arquitecto de Software. Analiza el código AS/400 y genera un PLAN DE MIGRACIÓN. 
Identifica comandos FTP y describe qué ID_INTERFAZ y ARCHIVO se usarán. NO generes código todavía."""

SYSTEM_PROMPT_REFACTOR = """Actúa como Desarrollador Senior de RPGLE/CL. Refactoriza siguiendo el plan aprobado.
Usa CALL PGM(SFTP_CTRL_CL) PARM('ID' 'FILE'). Si fallas, el compilador te avisará."""

# --- FUNCIONES DE AGENTE ---

def get_ai_response(prompt, system_role):
    resp = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "system", "content": system_role}, {"role": "user", "content": prompt}],
        temperature=0
    )
    return resp.choices[0].message.content

def simulate_compiler(code):
    """Lógica de validación sintáctica (Self-Healing)"""
    errors = []
    if "FIXME" in code: errors.append("Existen placeholders sin resolver.")
    if "STRTCPFTP" in code: errors.append("El comando antiguo STRTCPFTP no fue eliminado.")
    return (len(errors) == 0, errors)

# --- FLUJO HUMAN-IN-THE-LOOP (HITL) ---

# PASO 1: Carga de Archivo
if st.session_state.step == "upload":
    uploaded_file = st.file_uploader("Sube el componente legacy", type=['rpgle', 'clp'])
    if uploaded_file and client:
        st.session_state.source_code = uploaded_file.read().decode('utf-8')
        if st.button("🔍 Generar Plan de Análisis"):
            with st.spinner("Agente analizando código..."):
                st.session_state.plan = get_ai_response(st.session_state.source_code, SYSTEM_PROMPT_PLANNER)
                st.session_state.step = "validate_plan"
                st.rerun()

# PASO 2: Validación Humana del Plan
elif st.session_state.step == "validate_plan":
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📄 Código Original")
        st.code(st.session_state.source_code)
    with col2:
        st.subheader("📋 Plan Proyectado (HITL)")
        st.info(st.session_state.plan)
        
        st.markdown("---")
        if st.button("✅ Aprobar y Refactorizar"):
            st.session_state.step = "refactor"
            st.rerun()
        if st.button("🔄 Rechazar y Reintentar"):
            st.session_state.step = "upload"
            st.rerun()

# PASO 3: Ejecución con Autocuración
elif st.session_state.step == "refactor":
    st.subheader("🚀 Ejecutando Refactorización Atómica")
    
    with st.status("Ciclo de Autocuración en progreso...") as status:
        current_attempt = 0
        code_to_verify = st.session_state.source_code
        
        while current_attempt <= max_retries:
            st.write(f"Intento {current_attempt + 1}: Generando código...")
            refactored = get_ai_response(f"Plan: {st.session_state.plan}\nCódigo: {code_to_verify}", SYSTEM_PROMPT_REFACTOR)
            
            st.write("Verificando con Agente Compilador...")
            success, errors = simulate_compiler(refactored)
            
            if success:
                status.update(label="✅ Refactorización exitosa y validada.", state="complete")
                st.session_state.final_code = refactored
                break
            else:
                st.warning(f"Errores detectados: {errors}")
                code_to_verify = f"Código previo: {refactored}\nErrores a corregir: {errors}"
                current_attempt += 1
        
        if current_attempt > max_retries:
            status.update(label="❌ Falló la autocuración tras múltiples intentos.", state="error")

    st.subheader("Resultado Final")
    st.code(st.session_state.final_code)
    
    if st.button("🏁 Finalizar y Nueva Migración"):
        st.session_state.step = "upload"
        st.rerun()