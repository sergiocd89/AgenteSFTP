import streamlit as st
import time
import uuid
from core.infrastructure import backend_api_client
from core.login import run_backend_operation_with_retry
from core.logger import get_logger, log_operation
from core.ui.ai_presenter import run_llm_text
from core.utils import load_agent_prompt, step_header


LOGGER = get_logger(__name__)


def _run_workflow_step(step: str, prompt_file: str, source_input: str, context: str = "") -> str:
    """Ejecuta step COBOL->Python por backend y mantiene fallback local."""
    if backend_api_client.is_backend_enabled() and st.session_state.get("backend_access_token"):
        request_id = uuid.uuid4().hex[:12]
        started_at = time.perf_counter()
        ok, payload = run_backend_operation_with_retry(
            lambda token: backend_api_client.execute_workflow_step(
                token=token,
                workflow="cobol_python",
                step=step,
                source_input=source_input,
                context=context,
                model=st.session_state.model_name,
                temp=st.session_state.temp,
            )
        )
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        error_code = None
        if isinstance(payload, dict):
            error_code = payload.get("error_code")
        log_operation(
            LOGGER,
            operation="workflow_step_backend",
            success=bool(ok),
            error_code=str(error_code) if error_code else None,
            details=f"request_id={request_id} workflow=cobol_python step={step} duration_ms={duration_ms}",
        )
        if ok and isinstance(payload, dict):
            return str(payload.get("content") or "No se pudo obtener respuesta del backend en este paso.")

    sys_role = load_agent_prompt(prompt_file)
    result = run_llm_text(
        sys_role,
        source_input,
        st.session_state.model_name,
        st.session_state.temp,
    )
    return result or "No se pudo obtener respuesta del modelo en este paso."

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
                st.session_state.cobol_analysis = _run_workflow_step(
                    step="analyze",
                    prompt_file="01_analyst_CobolToPython.md",
                    source_input=st.session_state.cobol_source_code,
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
            context = f"Código COBOL:\n{st.session_state.cobol_source_code}\n\nAnálisis:\n{st.session_state.cobol_analysis}"
            st.session_state.cobol_arch_plan = _run_workflow_step(
                step="architect",
                prompt_file="02_architect_CobolToPython.md",
                source_input=context,
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
                context = f"Plan Aprobado:\n{st.session_state.cobol_arch_plan}\n\nFuente Original:\n{st.session_state.cobol_source_code}"
                st.session_state.cobol_python_code = _run_workflow_step(
                    step="develop",
                    prompt_file="03_developer_CobolToPython.md",
                    source_input=context,
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
            st.session_state.cobol_audit_report = _run_workflow_step(
                step="audit",
                prompt_file="04_auditor_CobolToPython.md",
                source_input=st.session_state.cobol_python_code,
            )

        with st.expander("🛡️ Ver Informe de Auditoría"):
            st.warning(st.session_state.cobol_audit_report)

        st.download_button("🐍 Descargar código Python", st.session_state.cobol_python_code, file_name="migrated_logic.py")

        if st.button("🔄 Nueva Migración COBOL"):
            for key in state_keys: st.session_state[f"cobol_{key}"] = state_keys[key]
            st.rerun()