import streamlit as st
import openai
import os
import hashlib
import hmac
from pathlib import Path
from dotenv import load_dotenv

# Cargamos variables de entorno una sola vez
load_dotenv()

# --- 0. AUTENTICACIÓN ---
_USERS: dict[str, str] = {
    "sergio.cuevas.d": hashlib.sha256("abcd.1234".encode()).hexdigest(),
    "carlos.ramirez":  hashlib.sha256("abcd.1234".encode()).hexdigest(),
}

def check_credentials(username: str, password: str) -> bool:
    """Verifica credenciales con comparación segura contra timing attacks."""
    stored_hash = _USERS.get(username)
    if not stored_hash:
        return False
    input_hash = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(stored_hash, input_hash)

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
def apply_custom_theme(theme: str) -> None:
    # Paleta institucional (aprox.) Scotiabank Chile
    scotia_red = "#ED0722"
    scotia_red_hover = "#C7051C"

    if theme == "Dark Mode":
        bg = "#121212"
        surface = "#1E1E1E"
        text = "#F5F5F5"
        muted = "#BDBDBD"
        border = "#2C2C2C"
    else:  # Light Mode
        bg = "#F7F7F7"
        surface = "#FFFFFF"
        text = "#333333"
        muted = "#666666"
        border = "#E6E6E6"

    st.markdown(
        f"""
        <style>
            .stApp {{
                background-color: {bg};
                color: {text};
            }}

            section[data-testid="stSidebar"] {{
                background-color: {surface};
                border-right: 2px solid {scotia_red};
            }}

            h1, h2, h3, h4, h5, h6, p, label, span, div {{
                color: {text};
            }}

            .stButton > button {{
                border-radius: 8px;
                border: 1px solid {border};
            }}

            .stButton > button[kind="primary"] {{
                background-color: {scotia_red};
                color: #FFFFFF;
                border: 1px solid {scotia_red};
                font-weight: 600;
            }}

            .stButton > button[kind="primary"]:hover {{
                background-color: {scotia_red_hover};
                border-color: {scotia_red_hover};
            }}

            div[data-testid="stVerticalBlockBorderWrapper"] {{
                background-color: {surface};
                border: 1px solid {border} !important;
                border-radius: 10px;
            }}

            hr {{
                border-color: {border};
            }}

            small, .stCaption {{
                color: {muted} !important;
            }}
        </style>
        """,
        unsafe_allow_html=True
    )

def step_header(text: str):
    """Genera un encabezado visual consistente para los pasos del pipeline."""
    st.markdown(f'### {text}')
    st.divider()