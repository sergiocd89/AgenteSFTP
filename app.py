import streamlit as st
import openai

# Configuración de la Interfaz
st.set_page_config(page_title="AS/400 SFTP Refactor Agent", layout="wide")
st.title("🤖 Agente de Migración FTP a SFTP (IBM i)")

# Configuración de API Key en la barra lateral
with st.sidebar:
    openai_key = st.text_input("OpenAI API Key", type="password")
    model_name = st.selectbox("Modelo", ["gpt-4o", "gpt-4-turbo"])

# Prompt de sistema
SYSTEM_PROMPT = """
Actúa como un experto en AS/400, RPGLE, COBOL y CL. 
Tu objetivo es refactorizar código legacy que utiliza comandos FTP nativos 
y sustituirlos por llamadas al nuevo motor centralizado de SFTP.

REGLAS DE TRANSFORMACIÓN:
1. Localiza comandos STRTCPFTP o bloques de código que generen archivos INPUT para FTP.
2. Sustituye esos bloques por una llamada (CALL) al programa controlador 'SFTP_CTRL_CL'.
3. Los parámetros del nuevo CALL deben ser: (ID_INTERFAZ, NOMBRE_ARCHIVO).
4. Mantén la lógica de negocio intacta, solo cambia la capa de transporte.
5. Si el código fuente es RPGLE (Free o Fixed), usa la sintaxis adecuada.
6. Comenta el código antiguo indicando: '* Migrado a SFTP por Agente IA'.
"""


def refactor_code(source_code, api_key, model_name):
    # configura el cliente con la nueva API (openai>=1.0.0)
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Refactoriza el siguiente código fuente de AS/400:\n\n{source_code}"}
        ],
        temperature=0
    )
    # campo 'choices' estructura igual
    return resp.choices[0].message.content


# Área de Carga de Archivos
uploaded_file = st.file_uploader("Sube el componente (.rpgle, .clp, .txt)", type=['rpgle', 'clp', 'txt', 'cbl'])

if uploaded_file and openai_key:
    source_text = uploaded_file.read().decode('utf-8')
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Código Original")
        st.code(source_text, language='sql')

    if st.button("🚀 Refactorizar a SFTP"):
        with st.spinner("Analizando y refactorizando..."):
            try:
                result = refactor_code(source_text, openai_key, model_name)
                with col2:
                    st.subheader("Código Refactorizado")
                    st.code(result, language='sql')
                    st.success("Refactorización completada.")
            except Exception as e:
                st.error(f"Error: {str(e)}")
else:
    st.info("Por favor, ingresa tu API Key y sube un archivo para comenzar.")