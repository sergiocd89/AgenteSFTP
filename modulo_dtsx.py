import streamlit as st

from dtsx_generator import (
    build_dtsx_package,
    extract_database_connections,
    extract_sql_statements,
    infer_package_name,
    summarize_connections,
)
from utils import call_llm, load_agent_prompt, step_header


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
                sys_role = load_agent_prompt("01_analyst_CobolToDtsx.md")
                st.session_state.dtsx_analysis = call_llm(
                    sys_role,
                    st.session_state.dtsx_source_code,
                    st.session_state.model_name,
                    st.session_state.temp,
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
            sys_role = load_agent_prompt("02_architect_CobolToDtsx.md")
            context = (
                f"Codigo COBOL:\n{st.session_state.dtsx_source_code}\n\n"
                f"Analisis:\n{st.session_state.dtsx_analysis}"
            )
            st.session_state.dtsx_plan = call_llm(
                sys_role,
                context,
                st.session_state.model_name,
                st.session_state.temp,
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
                sys_role = load_agent_prompt("03_developer_CobolToDtsx.md")
                context = (
                    f"Plan aprobado:\n{st.session_state.dtsx_plan}\n\n"
                    f"Fuente COBOL:\n{st.session_state.dtsx_source_code}"
                )
                st.session_state.dtsx_developer_notes = call_llm(
                    sys_role,
                    context,
                    st.session_state.model_name,
                    st.session_state.temp,
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
            sys_role = load_agent_prompt("04_auditor_CobolToDtsx.md")
            audit_context = (
                f"Plan:\n{st.session_state.dtsx_plan}\n\n"
                f"Blueprint:\n{st.session_state.dtsx_developer_notes}\n\n"
                f"DTSX:\n{st.session_state.dtsx_dtsx_content}"
            )
            st.session_state.dtsx_audit_report = call_llm(
                sys_role,
                audit_context,
                st.session_state.model_name,
                st.session_state.temp,
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