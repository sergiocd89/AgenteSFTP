import streamlit as st
from core.utils import call_llm, load_agent_prompt, step_header

def show_cobol_migration():
    st.title("🐍 Migrador Cobol a Python")
    st.caption("Modernización de lógica de negocio legacy a microservicios modernos")

    # --- 1. MANEJO DE ESTADO LOCAL (Prefijo 'cobol_') ---
    # Inicializamos las claves necesarias para este módulo si no existen
    state_keys = {
        "current_step": 1,
        "source_code": "",
        "analysis": "",
        "arch_plan": "",
        "python_code": "",
        "audit_report": ""
    }

    for key, default_value in state_keys.items():
        if f"cobol_{key}" not in st.session_state:
            st.session_state[f"cobol_{key}"] = default_value

    # --- 2. PASO 1: CARGA ---
    step_header("Paso 1: Carga de Código Fuente")
    if st.session_state.cobol_current_step == 1:
        with st.container(border=True):
            uploaded_file = st.file_uploader("Subir archivo COBOL (.cbl, .cob)", type=["cbl", "cob", "txt"])
            if uploaded_file:
                st.session_state.cobol_source_code = uploaded_file.read().decode("utf-8")
                st.success("Archivo COBOL detectado.")
                if st.button("Iniciar Análisis ➔", use_container_width=True):
                    st.session_state.cobol_current_step = 2
                    st.rerun()
    elif st.session_state.cobol_source_code:
        st.success("✅ Código fuente COBOL cargado.")

    # --- 3. PASO 2: ANÁLISIS ---
    if st.session_state.cobol_current_step >= 2:
        step_header("Paso 2: Análisis de Lógica y Dependencias")
        if not st.session_state.cobol_analysis:
            if st.button("Ejecutar Agente Analista"):
                sys_role = load_agent_prompt("01_analyst_CobolToPython.md")
                st.session_state.cobol_analysis = call_llm(
                    sys_role, st.session_state.cobol_source_code, 
                    st.session_state.model_name, st.session_state.temp
                )
                st.rerun()
        
        if st.session_state.cobol_analysis:
            st.info(st.session_state.cobol_analysis)
            if st.session_state.cobol_current_step == 2:
                if st.button("Continuar a Planificación ➔"):
                    st.session_state.cobol_current_step = 3
                    st.rerun()

    # --- 4. PASO 3: PLANIFICACIÓN (Editable) ---
    if st.session_state.cobol_current_step >= 3:
        step_header("Paso 3: Propuesta Arquitectónica (Python)")
        if not st.session_state.cobol_arch_plan:
            sys_role = load_agent_prompt("02_architect_CobolToPython.md")
            context = f"Código COBOL:\n{st.session_state.cobol_source_code}\n\nAnálisis:\n{st.session_state.cobol_analysis}"
            st.session_state.cobol_arch_plan = call_llm(
                sys_role, context, st.session_state.model_name, st.session_state.temp
            )
        
        st.session_state.cobol_arch_plan = st.text_area(
            "Plan de Migración (Puedes editarlo antes de generar):", 
            value=st.session_state.cobol_arch_plan, height=250
        )
        
        if st.session_state.cobol_current_step == 3:
            if st.button("Aprobar y Generar Código Python ➔"):
                st.session_state.cobol_current_step = 4
                st.rerun()

    # --- 5. PASO 4: EJECUCIÓN (GENERACIÓN) ---
    if st.session_state.cobol_current_step >= 4:
        step_header("Paso 4: Generación de Código Python")
        if not st.session_state.cobol_python_code:
            with st.spinner("Traduciendo lógica COBOL a Python..."):
                sys_role = load_agent_prompt("03_developer_CobolToPython.md")
                context = f"Plan Aprobado:\n{st.session_state.cobol_arch_plan}\n\nFuente Original:\n{st.session_state.cobol_source_code}"
                st.session_state.cobol_python_code = call_llm(
                    sys_role, context, st.session_state.model_name, st.session_state.temp
                )
                st.rerun()
        
        st.code(st.session_state.cobol_python_code, language="python")
        
        if st.session_state.cobol_current_step == 4:
            if st.button("Validar y Auditar ➔"):
                st.session_state.cobol_current_step = 5
                st.rerun()

    # --- 6. PASO 5: AUDITORÍA Y ENTREGA ---
    if st.session_state.cobol_current_step >= 5:
        step_header("Paso 5: Validación y Entrega Final")
        
        # Auditoría automática si no existe
        if not st.session_state.cobol_audit_report:
            sys_role = load_agent_prompt("04_auditor_CobolToPython.md")
            st.session_state.cobol_audit_report = call_llm(
                sys_role, st.session_state.cobol_python_code, 
                st.session_state.model_name, st.session_state.temp
            )

        with st.expander("🛡️ Ver Informe de Auditoría"):
            st.warning(st.session_state.cobol_audit_report)

        st.download_button("🐍 Descargar código Python", st.session_state.cobol_python_code, file_name="migrated_logic.py")

        if st.button("🔄 Nueva Migración COBOL"):
            for key in state_keys: st.session_state[f"cobol_{key}"] = state_keys[key]
            st.rerun()