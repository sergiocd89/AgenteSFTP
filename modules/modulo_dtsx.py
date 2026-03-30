import streamlit as st
import time

from modules.dtsx_generator import (
    build_dtsx_package,
    extract_database_connections,
    extract_sql_statements,
    infer_package_name,
    summarize_connections,
)
from core.infrastructure import backend_api_client
from core.login import run_backend_operation_with_retry
from core.logger import get_logger, log_operation
from core.ui.ai_presenter import run_llm_text
from core.utils import load_agent_prompt, step_header


LOGGER = get_logger(__name__)


def _run_workflow_step(step: str, prompt_file: str, source_input: str, context: str = "") -> str:
    """Ejecuta step COBOL->DTSX por backend y mantiene fallback local."""
    if backend_api_client.is_backend_enabled() and st.session_state.get("backend_access_token"):
        started_at = time.perf_counter()
        ok, payload = run_backend_operation_with_retry(
            lambda token: backend_api_client.execute_workflow_step(
                token=token,
                workflow="cobol_dtsx",
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
            details=f"workflow=cobol_dtsx step={step} duration_ms={duration_ms}",
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


def show_dtsx_generation():
    st.title("📦 Generador COBOL a DTSX")
    st.caption("Construcción asistida de paquetes SSIS para flujos COBOL con SQL Server y Sybase")

    state_keys = {
        "current_step": 1,
        "source_code": "",
        "source_filename": "",
        "package_name": "",
        "analysis": "",
        "plan": "",
        "developer_notes": "",
        "dtsx_content": "",
        "audit_report": "",
    }

    for key, default_value in state_keys.items():
        if f"dtsx_{key}" not in st.session_state:
            st.session_state[f"dtsx_{key}"] = default_value

    step_header("Paso 1: Carga de COBOL con acceso a bases de datos")
    if st.session_state.dtsx_current_step == 1:
        with st.container(border=True):
            uploaded_file = st.file_uploader(
                "Subir fuente COBOL con SQL embebido (.cbl, .cob, .txt)",
                type=["cbl", "cob", "txt"],
            )
            if uploaded_file:
                source_code = uploaded_file.read().decode("utf-8")
                st.session_state.dtsx_source_code = source_code
                st.session_state.dtsx_source_filename = uploaded_file.name
                if not st.session_state.dtsx_package_name:
                    st.session_state.dtsx_package_name = infer_package_name(uploaded_file.name)

                connections = extract_database_connections(source_code)
                sql_statements = extract_sql_statements(source_code)
                if connections:
                    st.markdown("**Conexiones detectadas**")
                    st.markdown(summarize_connections(connections))
                else:
                    st.warning(
                        "No se detectaron cadenas de conexión completas. El paquete se generará con placeholders editables."
                    )

                st.info(f"Bloques EXEC SQL detectados: {len(sql_statements)}")
                st.session_state.dtsx_package_name = st.text_input(
                    "Nombre del paquete DTSX",
                    value=st.session_state.dtsx_package_name,
                )
                if st.button("Iniciar análisis DTSX ➔", use_container_width=True):
                    st.session_state.dtsx_current_step = 2
                    st.rerun()
    elif st.session_state.dtsx_source_code:
        st.success("✅ Fuente COBOL cargada para generación DTSX.")

    if st.session_state.dtsx_current_step >= 2:
        step_header("Paso 2: Análisis de accesos SQL y dependencias")
        if not st.session_state.dtsx_analysis:
            if st.button("Ejecutar agente analista DTSX"):
                st.session_state.dtsx_analysis = _run_workflow_step(
                    step="analyze",
                    prompt_file="01_analyst_CobolToDtsx.md",
                    source_input=st.session_state.dtsx_source_code,
                )
                st.rerun()

        if st.session_state.dtsx_analysis:
            st.info(st.session_state.dtsx_analysis)
            if st.session_state.dtsx_current_step == 2:
                if st.button("Continuar a diseño del paquete ➔"):
                    st.session_state.dtsx_current_step = 3
                    st.rerun()

    if st.session_state.dtsx_current_step >= 3:
        step_header("Paso 3: Diseño de paquete SSIS")
        if not st.session_state.dtsx_plan:
            context = (
                f"Codigo COBOL:\n{st.session_state.dtsx_source_code}\n\n"
                f"Analisis:\n{st.session_state.dtsx_analysis}"
            )
            st.session_state.dtsx_plan = _run_workflow_step(
                step="architect",
                prompt_file="02_architect_CobolToDtsx.md",
                source_input=context,
            )

        st.session_state.dtsx_plan = st.text_area(
            "Plan del paquete DTSX (editable)",
            value=st.session_state.dtsx_plan,
            height=250,
        )

        if st.session_state.dtsx_current_step == 3:
            if st.button("Aprobar y generar DTSX ➔"):
                st.session_state.dtsx_current_step = 4
                st.rerun()

    if st.session_state.dtsx_current_step >= 4:
        step_header("Paso 4: Generación de paquete DTSX")
        if not st.session_state.dtsx_developer_notes:
            with st.spinner("Definiendo estructura técnica del paquete SSIS..."):
                context = (
                    f"Plan aprobado:\n{st.session_state.dtsx_plan}\n\n"
                    f"Fuente COBOL:\n{st.session_state.dtsx_source_code}"
                )
                st.session_state.dtsx_developer_notes = _run_workflow_step(
                    step="develop",
                    prompt_file="03_developer_CobolToDtsx.md",
                    source_input=context,
                )

        if not st.session_state.dtsx_dtsx_content:
            st.session_state.dtsx_dtsx_content = build_dtsx_package(
                st.session_state.dtsx_source_code,
                st.session_state.dtsx_package_name,
                st.session_state.dtsx_developer_notes,
            )

        with st.expander("🧭 Ver blueprint técnico del paquete"):
            st.info(st.session_state.dtsx_developer_notes)

        st.code(st.session_state.dtsx_dtsx_content, language="xml")

        if st.session_state.dtsx_current_step == 4:
            if st.button("Auditar paquete generado ➔"):
                st.session_state.dtsx_current_step = 5
                st.rerun()

    if st.session_state.dtsx_current_step >= 5:
        step_header("Paso 5: Auditoría y entrega")
        if not st.session_state.dtsx_audit_report:
            audit_context = (
                f"Plan:\n{st.session_state.dtsx_plan}\n\n"
                f"Blueprint:\n{st.session_state.dtsx_developer_notes}\n\n"
                f"DTSX:\n{st.session_state.dtsx_dtsx_content}"
            )
            st.session_state.dtsx_audit_report = _run_workflow_step(
                step="audit",
                prompt_file="04_auditor_CobolToDtsx.md",
                source_input=audit_context,
            )

        with st.expander("🛡️ Ver informe de auditoría DTSX"):
            st.warning(st.session_state.dtsx_audit_report)

        st.download_button(
            "📥 Descargar paquete DTSX",
            st.session_state.dtsx_dtsx_content,
            file_name=f"{st.session_state.dtsx_package_name}.dtsx",
            mime="application/xml",
        )

        if st.button("🔄 Nueva generación DTSX"):
            for key, default_value in state_keys.items():
                st.session_state[f"dtsx_{key}"] = default_value
            st.rerun()