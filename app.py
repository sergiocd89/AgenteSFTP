import streamlit as st
import openai
import os
from dotenv import load_dotenv

# 1. Configuración Inicial
load_dotenv()

# helper para crear cliente de OpenAI bajo demanda (evita crear uno en import)
_client: openai.OpenAI | None = None

def _get_client(api_key: str | None = None) -> openai.OpenAI:
    global _client
    if _client is None:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI API key is required")
        _client = openai.OpenAI(api_key=key)
    return _client

st.set_page_config(page_title="AS/400 Legacy Agent Migrator", layout="wide", page_icon="🤖")

# --- ESTILOS UX ---
st.markdown("""
    <style>
    .step-header { color: #1E88E5; font-weight: bold; font-size: 24px; margin-top: 20px; border-bottom: 2px solid #1E88E5; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1E88E5; color: white; }
    </style>
    """, unsafe_allow_html=True)

# función exportada para uso como módulo

def refactor_code(text: str, *, api_key: str | None = None, model_name: str = "gpt-4o") -> str:
    """Refactoriza un fragmento de código legacy usando la API de OpenAI.

    Este helper reproduce la lógica mínima que usa la aplicación Streamlit,
    de manera que pueda importarse desde otros módulos (y desde tests).

    Args:
        text: código o descripción de entrada que se enviará al modelo.
        api_key: clave de OpenAI. Si no se proporciona, se intentará leerla de
            la variable de entorno ``OPENAI_API_KEY``.
        model_name: modelo a solicitar (por defecto ``gpt-4o``).

    Returns:
        Texto devuelto por el modelo, normalmente el código refactorizado.
    """
    # determino la clave
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI API key is required for refactor_code")

    client = _get_client(api_key=key)
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "Actúa como migrador de FTP a SFTP."},
            {"role": "user", "content": text},
        ],
    )
    return resp.choices[0].message.content

# --- MANEJO DE ESTADO ---
if "current_step" not in st.session_state: st.session_state.current_step = 1
if "source_code" not in st.session_state: st.session_state.source_code = ""
if "plan" not in st.session_state: st.session_state.plan = ""
if "preview_code" not in st.session_state: st.session_state.preview_code = ""
if "final_code" not in st.session_state: st.session_state.final_code = ""

def get_ai_response(prompt, system_role):
    try:
        client = _get_client()
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
        st.error(f"Error: {e}")
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Configuración de Migración")
    st.session_state.model_name = st.selectbox("Modelo", ["gpt-4o", "gpt-4-turbo"])
    st.session_state.temp = st.slider("Precisión vs Creatividad", 0.0, 1.0, 0.0)
    st.session_state.max_retries = st.number_input("Reintentos de Autocuración", 1, 5, 3)
    
    st.divider()
    st.session_state.target_format = st.selectbox(
        "Formato Destino",
        ["RPGLE Free (**FREE)", "Python (Paramiko/SFTP)", "SQLRPGLE Modern"]
    )
    st.session_state.strict_mode = st.toggle("Validar protocolo SFTP", value=True)

st.title("🤖 Migrador de Protocolos: FTP ➡️ SFTP")

# --- PASO 1: INGESTA DE CÓDIGO ---
st.markdown('<p class="step-header">Paso 1: Ingesta de Código Fuente</p>', unsafe_allow_html=True)
with st.container(border=True):
    if st.session_state.current_step == 1:
        file = st.file_uploader("Sube fuentes con comandos FTP", type=['rpgle', 'clp', 'txt'])
        if file and st.button("Analizar Migración SFTP"):
            st.session_state.source_code = file.read().decode('utf-8')
            with st.spinner("Diseñando arquitectura SFTP segura..."):
                # ACTUALIZACIÓN: Instrucción explícita de cambio de protocolo
                sys_role = (f"Actúa como Arquitecto de Ciberseguridad e IBM i. Tu tarea prioritaria es "
                            f"identificar comandos FTP (SEND, GET, MGET) y reemplazarlos por una "
                            f"arquitectura SFTP segura en {st.session_state.target_format}. "
                            f"Considera el manejo de llaves SSH y CCSID.")
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
            edited_plan = st.text_area("Revisa el plan (verifica llaves SSH y rutas):", value=st.session_state.plan, height=200)
            if st.button("Generar Código Modernizado"):
                st.session_state.plan = edited_plan
                with st.spinner("Escribiendo lógica SFTP..."):
                    sys_role = "Genera solo el código. Si es Python, usa paramiko. Si es RPGLE, usa mandatos SSH/SFTP."
                    prompt = f"Plan: {st.session_state.plan}\n\nCódigo Original:\n{st.session_state.source_code}"
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
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Legacy (FTP)")
                st.code(st.session_state.source_code)
            with col2:
                st.subheader("Moderno (SFTP)")
                st.code(st.session_state.preview_code)
            if st.session_state.current_step == 3:
                if st.button("Validar Seguridad y Autocuración"):
                    st.session_state.current_step = 4
                    st.rerun()
        else:
            st.success("Cambios aceptados por el usuario.")

# --- PASO 4: AUTOCURACIÓN (Lógica SFTP) ---
if st.session_state.current_step >= 4:
    st.markdown('<p class="step-header">Paso 4: Validación de Reglas SFTP</p>', unsafe_allow_html=True)
    if not st.session_state.final_code:
        with st.status("Validando seguridad del túnel...", expanded=True) as status:
            current_code = st.session_state.preview_code
            for i in range(st.session_state.max_retries):
                errors = []
                # Reglas de Autocuración para SFTP
                if "FTP" in current_code.upper() and "SFTP" not in current_code.upper():
                    errors.append("Se detectó mención a 'FTP' cuando el destino debe ser 'SFTP'.")
                
                if "PYTHON" in st.session_state.target_format.upper():
                    if "PARAMIKO" not in current_code.upper():
                        errors.append("Falta la librería 'paramiko' para la gestión de SFTP.")
                
                if "RPG" in st.session_state.target_format.upper():
                    if "PUT" in current_code.upper() and "SFTP" not in current_code.upper():
                        errors.append("El comando PUT debe ejecutarse dentro de una sesión SFTP/SSH.")

                if not errors: break
                
                st.warning(f"Error detectado: {errors}")
                fix_prompt = f"Corrige estos fallos de protocolo: {errors}. Código:\n{current_code}"
                current_code = get_ai_response(fix_prompt, "Experto en protocolos SSH/SFTP.")
            
            st.session_state.final_code = current_code
            status.update(label="Migración completada con éxito.", state="complete")

    st.subheader("Resultado Final SFTP")
    st.code(st.session_state.final_code)
    st.download_button("Descargar Fuente Migrado", st.session_state.final_code)