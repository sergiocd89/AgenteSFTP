import streamlit as st
import openai
import os
from dotenv import load_dotenv

# 1. Configuración Inicial y Carga de Entorno
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=api_key) if api_key else None

st.set_page_config(page_title="AS/400 Legacy Agent Migrator", layout="wide", page_icon="🤖")

# --- ESTILOS UX PERSONALIZADOS ---
st.markdown("""
    <style>
    .step-header { color: #1E88E5; font-weight: bold; font-size: 24px; margin-top: 20px; border-bottom: 2px solid #1E88E5; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1E88E5; color: white; }
    .stProgress .st-bo { background-color: #1E88E5; }
    code { color: #e83e8c; }
    </style>
    """, unsafe_allow_html=True)

# --- MANEJO DE ESTADO (SESSION STATE) ---
if "current_step" not in st.session_state:
    st.session_state.current_step = 1
if "source_code" not in st.session_state:
    st.session_state.source_code = ""
if "plan" not in st.session_state:
    st.session_state.plan = ""
if "preview_code" not in st.session_state:
    st.session_state.preview_code = ""
if "final_code" not in st.session_state:
    st.session_state.final_code = ""

# --- FUNCIÓN DE COMUNICACIÓN CON EL AGENTE ---
def get_ai_response(prompt, system_role):
    try:
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
        st.error(f"Error en la API de OpenAI: {e}")
        return None

# --- BARRA LATERAL: CONFIGURACIÓN TÉCNICA ---
with st.sidebar:
    st.title("⚙️ Panel de Control")
    st.subheader("Parámetros del Agente")
    
    st.session_state.model_name = st.selectbox(
        "Cerebro de IA", 
        ["gpt-4o", "gpt-4-turbo"],
        help="Se recomienda gpt-4o para lógica compleja de RPG/COBOL."
    )
    
    col_temp, col_retries = st.columns(2)
    with col_temp:
        st.session_state.temp = st.slider("Temperature", 0.0, 1.0, 0.0, 0.1, help="0.0 = Precisión técnica, 1.0 = Creatividad.")
    with col_retries:
        st.session_state.max_retries = st.number_input("Max Retries", 1, 5, 3, help="Intentos de autocuración en caso de errores.")

    st.divider()
    st.subheader("Especificaciones AS/400")
    st.session_state.target_format = st.selectbox(
        "Formato Destino",
        ["RPGLE Free (**FREE)", "SQLRPGLE Modern", "Java (Spring Boot)", "Python (FastAPI)"]
    )
    st.session_state.strict_mode = st.toggle("Modo Estricto (Linter)", value=True)
    
    st.divider()
    st.write(f"Etapa actual: **{st.session_state.current_step} de 4**")
    st.progress(st.session_state.current_step / 4)
    
    if st.button("Resetear Proceso"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

st.title("🤖 Agente Experto en Migración AS/400")
st.caption("Modernización de código heredado mediante Agentic Workflows y Autocuración.")

# --- PASO 1: INGESTA DE CÓDIGO ---
st.markdown('<p class="step-header">Paso 1: Ingesta de Código Fuente</p>', unsafe_allow_html=True)
with st.container(border=True):
    if st.session_state.current_step == 1:
        file = st.file_uploader("Sube código fuente (RPG, CL, COBOL)", type=['rpgle', 'clp', 'cbl', 'txt'])
        if file and st.button("Analizar y Generar Plan"):
            st.session_state.source_code = file.read().decode('utf-8')
            with st.spinner("El Arquitecto está analizando la estructura..."):
                sys_role = f"Actúa como Arquitecto de Software experto en IBM i (AS/400). Tu objetivo es analizar código y planear una migración hacia {st.session_state.target_format}."
                st.session_state.plan = get_ai_response(st.session_state.source_code, sys_role)
                st.session_state.current_step = 2
                st.rerun()
    else:
        st.success(f"✅ Archivo cargado correctamente. Tamaño: {len(st.session_state.source_code)} caracteres.")

# --- PASO 2: PLANIFICACIÓN DE ARQUITECTURA ---
if st.session_state.current_step >= 2:
    st.markdown('<p class="step-header">Paso 2: Planificación de Arquitectura</p>', unsafe_allow_html=True)
    with st.container(border=True):
        if st.session_state.current_step == 2:
            edited_plan = st.text_area("Revisa el plan de migración propuesto:", value=st.session_state.plan, height=250)
            if st.button("Generar Previsualización de Código"):
                st.session_state.plan = edited_plan
                with st.spinner("Generando primera versión del código..."):
                    sys_role = f"Genera código refactorizado en {st.session_state.target_format}. No incluyas explicaciones, solo el código limpio."
                    prompt = f"Plan: {st.session_state.plan}\n\nCódigo Fuente Original:\n{st.session_state.source_code}"
                    st.session_state.preview_code = get_ai_response(prompt, sys_role)
                    st.session_state.current_step = 3
                    st.rerun()
        else:
            st.info("Plan de arquitectura aprobado.")

# --- PASO 3: PREVISUALIZACIÓN Y COMPARACIÓN ---
if st.session_state.current_step >= 3:
    st.markdown('<p class="step-header">Paso 3: Previsualización de Diferencias</p>', unsafe_allow_html=True)
    with st.container(border=True):
        if st.session_state.current_step == 3:
            col_orig, col_mig = st.columns(2)
            with col_orig:
                st.subheader("Código Original")
                st.code(st.session_state.source_code, language="python") # Resaltado genérico para RPG
            with col_mig:
                st.subheader("Propuesta Inicial")
                st.code(st.session_state.preview_code, language="python")
            
            if st.button("Confirmar y Ejecutar Ciclo de Autocuración"):
                st.session_state.current_step = 4
                st.rerun()
        else:
            st.success("Cambios aceptados por el usuario.")

# --- PASO 4: REFACTORIZACIÓN FINAL Y AUTOCURACIÓN ---
if st.session_state.current_step >= 4:
    st.markdown('<p class="step-header">Paso 4: Validación y Autocuración Final</p>', unsafe_allow_html=True)
    
    with st.container(border=True):
        if not st.session_state.final_code:
            with st.status("Iniciando validación sintáctica...", expanded=True) as status:
                
                current_code = st.session_state.preview_code
                
                for i in range(st.session_state.max_retries):
                    st.write(f"🔄 **Ciclo {i+1}:** Analizando reglas críticas...")
                    
                    # Simulación de Linter para IBM i
                    errors = []
                    if "**FREE" in st.session_state.target_format and "**FREE" not in current_code.upper():
                        errors.append("Falta directiva obligatoria **FREE en línea 1.")
                    if "SQL" in st.session_state.target_format and "EXEC SQL" in current_code.upper() and ";" not in current_code:
                        errors.append("Sentencia EXEC SQL detectada sin terminador ';'.")
                    if current_code.count("IF") != current_code.count("ENDIF"):
                        errors.append("Bloques condicionales (IF/ENDIF) desbalanceados.")

                    if not errors or not st.session_state.strict_mode:
                        st.write("✅ El código cumple con las reglas básicas de validación.")
                        break
                    
                    st.warning(f"Errores detectados en ciclo {i+1}: {errors}")
                    
                    # Prompt de corrección
                    fix_prompt = f"El código tiene estos errores: {errors}. Corrígelos manteniendo el resto igual:\n\n{current_code}"
                    current_code = get_ai_response(fix_prompt, f"Eres un experto en {st.session_state.target_format} Senior. Tu única tarea es corregir errores sintácticos.")
                
                st.session_state.final_code = current_code
                status.update(label="Proceso de autocuración finalizado.", state="complete")
        
        st.subheader("Código Final Optimizado")
        st.code(st.session_state.final_code, language="python")
        
        file_ext = "rpgle" if "RPG" in st.session_state.target_format else "java" if "Java" in st.session_state.target_format else "py"
        st.download_button(
            label="💾 Descargar Resultado Final",
            data=st.session_state.final_code,
            file_name=f"migrated_code.{file_ext}",
            mime="text/plain"
        )