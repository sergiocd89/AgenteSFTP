import streamlit as st
import openai
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargamos variables de entorno una sola vez
load_dotenv()

# --- 1. CLIENTE DE IA ---
@st.cache_resource
def get_openai_client():
    """Inicializa y cachea el cliente de OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("🔑 API Key no encontrada en el archivo .env")
        st.stop()
    return openai.OpenAI(api_key=api_key)

# --- 2. GESTIÓN DE PROMPTS ---
@st.cache_data
def load_agent_prompt(filename: str) -> str:
    """Carga las instrucciones del agente desde la carpeta .github/agents."""
    path = Path(".github/agents") / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "Eres un asistente experto en modernización legacy para IBM i."

# --- 3. LÓGICA DE COMUNICACIÓN (CORE) ---
def call_llm(system_role: str, user_content: str, model: str, temp: float):
    """
    Función unificada para llamadas a ChatCompletions.
    Usada por todos los módulos.
    """
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=model,
            temperature=temp,
            messages=[
                {"role": "system", "content": system_role},
                {"role": "user", "content": user_content}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"❌ Error en la llamada a la IA: {e}")
        return None

# --- 4. INTERFAZ Y ESTILO ---
def apply_custom_theme(theme_name: str):
    """Aplica el CSS según el tema elegido."""
    theme_file = "assets/dark_mode.css" if theme_name == "Dark Mode" else "assets/light_mode.css"
    if Path(theme_file).exists():
        with open(theme_file, "r") as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    else:
        st.sidebar.warning(f"⚠️ Archivo de estilo no encontrado: {theme_file}")

def step_header(text: str):
    """Genera un encabezado visual consistente para los pasos del pipeline."""
    st.markdown(f'### {text}')
    st.divider()