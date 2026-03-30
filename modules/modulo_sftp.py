import streamlit as st
import time
from core.infrastructure import backend_api_client
from core.login import run_backend_operation_with_retry
from core.logger import get_logger, log_operation
from core.observability import format_workflow_log_details, generate_request_id
from core.ui.ai_presenter import run_llm_text
from core.utils import load_agent_prompt, step_header


LOGGER = get_logger(__name__)


def _run_workflow_step(step: str, prompt_file: str, source_input: str, context: str = "") -> str:
    """Ejecuta step SFTP por backend y mantiene fallback local."""
    if backend_api_client.is_backend_enabled() and st.session_state.get("backend_access_token"):
        request_id = generate_request_id()
        started_at = time.perf_counter()
        ok, payload = run_backend_operation_with_retry(
            lambda token: backend_api_client.execute_workflow_step(
                token=token,
                workflow="sftp",
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
            details=format_workflow_log_details(request_id, "sftp", step, duration_ms),
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

def show_sftp_migration():
    st.title("🤖 Agente Migrador de Protocolos IBM i")
    st.caption("Modernización automática de FTP a SFTP mediante IA Agéntica")

    # --- 1. MANEJO DE ESTADO LOCAL ---
    # Inicializamos las claves necesarias para este módulo si no existen
    state_keys = {
        "current_step": 1,
        "source_code": "",
        "analysis": "",
        "plan": "",
        "execution_code": "",
        "validation_report": ""
    }

    for key, default_value in state_keys.items():
        if f"sftp_{key}" not in st.session_state:
            st.session_state[f"sftp_{key}"] = default_value

    # --- 2. PASO 1: CARGA ---
    step_header("Paso 1: Carga del Proyecto")
    if st.session_state.sftp_current_step == 1:
        with st.container(border=True):
            file = st.file_uploader("Sube fuentes AS/400 (RPGLE, CLP, SQLRPGLE)", type=['rpgle', 'clp', 'sqlrpgle'])
            if file and st.button("Iniciar Pipeline", use_container_width=True):
                st.session_state.sftp_source_code = file.read().decode('utf-8')
                st.session_state.sftp_current_step = 2
                st.rerun()
    elif st.session_state.sftp_source_code: 
        st.success("✅ Miembro fuente cargado correctamente.")

    # --- 3. PASO 2: ANÁLISIS ---
    if st.session_state.sftp_current_step >= 2:
        step_header("Paso 2: Análisis de Código Legacy")
        if st.session_state.sftp_current_step == 2:
            with st.spinner("Escaneando dependencias y comandos FTP..."):
                st.session_state.sftp_analysis = _run_workflow_step(
                    step="analyze",
                    prompt_file="01_analyst_AS400SFTP.md",
                    source_input=st.session_state.sftp_source_code,
                )
                st.session_state.sftp_current_step = 3
                st.rerun()
        st.info(st.session_state.sftp_analysis)

    # --- 4. PASO 3: PLANIFICACIÓN ---
    if st.session_state.sftp_current_step >= 3:
        step_header("Paso 3: Estrategia SFTP (Arquitectura)")
        if st.session_state.sftp_current_step == 3:
            with st.container(border=True):
                suggested_plan = _run_workflow_step(
                    step="architect",
                    prompt_file="02_architect_AS400SFTP.md",
                    source_input=st.session_state.sftp_analysis,
                )
                st.session_state.sftp_plan = st.text_area("Propuesta Técnica:", value=suggested_plan, height=200)
                if st.button("Aprobar y Generar Código", use_container_width=True):
                    st.session_state.sftp_current_step = 4
                    st.rerun()
        else:
            st.success("✅ Arquitectura definida.")

    # --- 5. PASO 4: EJECUCIÓN ---
    if st.session_state.sftp_current_step >= 4:
        step_header("Paso 4: Generación de Código Modernizado")
        if st.session_state.sftp_current_step == 4:
            with st.spinner("Escribiendo código RPGLE/CL con SFTP..."):
                prompt = f"Fuente Original:\n{st.session_state.sftp_source_code}\n\nPlan Aprobado:\n{st.session_state.sftp_plan}"
                st.session_state.sftp_execution_code = _run_workflow_step(
                    step="develop",
                    prompt_file="03_developer_AS400SFTP.md",
                    source_input=prompt,
                )
                st.session_state.sftp_current_step = 5
                st.rerun()
        st.code(st.session_state.sftp_execution_code, language='rpgle')

    # --- 6. PASO 5: VALIDACIÓN (AUDITORÍA) ---
    if st.session_state.sftp_current_step >= 5:
        step_header("Paso 5: Auditoría de Seguridad")
        if st.session_state.sftp_current_step == 5:
            with st.status("Verificando claves SSH y permisos...", expanded=True):
                st.session_state.sftp_validation_report = _run_workflow_step(
                    step="audit",
                    prompt_file="04_auditor_AS400SFTP.md",
                    source_input=st.session_state.sftp_execution_code,
                )
                st.session_state.sftp_current_step = 6
                st.rerun()
        st.warning(st.session_state.sftp_validation_report)

    # --- 7. PASO 6: ENTREGA ---
    if st.session_state.sftp_current_step >= 6:
        step_header("Paso 6: Entrega de Fuente Modernizada")
        st.download_button("📥 Descargar Fuente", st.session_state.sftp_execution_code, file_name="modernized_sftp.rpgle")
        
        if st.button("🔄 Iniciar Nueva Migración"):
            for key in state_keys: st.session_state[f"sftp_{key}"] = state_keys[key]
            st.rerun()