import streamlit as st
from utils import call_llm, load_agent_prompt, step_header


def _extract_text_from_file(uploaded_file) -> str:
    """Intenta extraer texto de archivos de contexto sin dependencias externas."""
    raw_bytes = uploaded_file.getvalue()
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    # Fallback defensivo para binarios: conserva solo caracteres decodificables.
    return raw_bytes.decode("utf-8", errors="ignore")


def _build_documents_context(uploaded_files) -> tuple[str, list[str]]:
    """Construye un bloque compacto de contexto con los documentos subidos."""
    if not uploaded_files:
        return "", []

    snippets = []
    loaded_docs = []
    max_chars_per_doc = 5000

    for file in uploaded_files:
        content = _extract_text_from_file(file).strip()
        if not content:
            continue

        truncated = content[:max_chars_per_doc]
        snippets.append(
            f"### Documento: {file.name}\n"
            f"{truncated}\n"
            f"\n"
            f"(Longitud usada: {len(truncated)} caracteres)"
        )
        loaded_docs.append(file.name)

    return "\n\n".join(snippets), loaded_docs


def _run_agent(agent_filename: str, user_content: str) -> str:
    """Ejecuta un agente por archivo de prompt y maneja fallback de errores."""
    sys_role = load_agent_prompt(agent_filename)
    result = call_llm(
        sys_role,
        user_content,
        st.session_state.model_name,
        st.session_state.temp,
    )
    return result or "No se pudo obtener respuesta del modelo en este paso."


def show_requirement_workflow():
    st.title("🧩 Requirement Workflow")
    st.caption("Pipeline agéntico para convertir requerimientos en un ticket listo para Jira/GitHub.")

    state_keys = {
        "current_step": 1,
        "requirement_text": "",
        "documents_context": "",
        "loaded_documents": [],
        "creator_output": "",
        "refiner_output": "",
        "editor_output": "",
        "diagram_output": "",
        "sizer_output": "",
        "qa_output": "",
        "issue_output": "",
    }

    for key, default_value in state_keys.items():
        state_key = f"reqwf_{key}"
        if state_key not in st.session_state:
            st.session_state[state_key] = default_value

    step_header("Paso 1: Ingreso del Requerimiento y Contexto")
    if st.session_state.reqwf_current_step == 1:
        with st.container(border=True):
            requirement_text = st.text_area(
                "Ingrese el requerimiento principal",
                value=st.session_state.reqwf_requirement_text,
                height=200,
                placeholder=(
                    "Ejemplo: Como supervisor de operaciones quiero aprobar transferencias "
                    "con doble validación para reducir fraudes."
                ),
            )

            uploaded_files = st.file_uploader(
                "Subir documentos de contexto (opcional)",
                type=["txt", "md", "log", "json", "yaml", "yml", "csv", "xml"],
                accept_multiple_files=True,
            )

            if st.button("Iniciar Workflow ➔", use_container_width=True, type="primary"):
                if not requirement_text.strip():
                    st.warning("Debe ingresar un requerimiento antes de continuar.")
                else:
                    docs_context, loaded_docs = _build_documents_context(uploaded_files)
                    st.session_state.reqwf_requirement_text = requirement_text.strip()
                    st.session_state.reqwf_documents_context = docs_context
                    st.session_state.reqwf_loaded_documents = loaded_docs
                    st.session_state.reqwf_current_step = 2
                    st.rerun()
    else:
        st.success("✅ Requerimiento base cargado.")
        if st.session_state.reqwf_loaded_documents:
            st.caption(
                "Documentos usados: "
                + ", ".join(st.session_state.reqwf_loaded_documents)
            )

    base_context = (
        f"## Requerimiento principal\n{st.session_state.reqwf_requirement_text}\n\n"
        f"## Documentos de contexto\n"
        f"{st.session_state.reqwf_documents_context or 'No se adjuntaron documentos.'}"
    )

    if st.session_state.reqwf_current_step >= 2:
        step_header("Paso 2: Agent 01 - Creator Use Case")
        if not st.session_state.reqwf_creator_output:
            if st.button("Generar Historia de Usuario Inicial"):
                st.session_state.reqwf_creator_output = _run_agent(
                    "Agent_Requirement_WorkFlow_01_Creator_Use_Case.md",
                    base_context,
                )
                st.rerun()

        if st.session_state.reqwf_creator_output:
            st.info(st.session_state.reqwf_creator_output)
            if st.session_state.reqwf_current_step == 2 and st.button("Continuar a Refinamiento ➔"):
                st.session_state.reqwf_current_step = 3
                st.rerun()

    if st.session_state.reqwf_current_step >= 3:
        step_header("Paso 3: Agent 02 - Refiner Use Case")
        if not st.session_state.reqwf_refiner_output:
            if st.button("Ejecutar Refinamiento INVEST"):
                input_refiner = (
                    f"Contexto original:\n{base_context}\n\n"
                    f"Historia inicial:\n{st.session_state.reqwf_creator_output}"
                )
                st.session_state.reqwf_refiner_output = _run_agent(
                    "Agent_Requirement_WorkFlow_02_Refiner_Use_Case.md",
                    input_refiner,
                )
                st.rerun()

        if st.session_state.reqwf_refiner_output:
            st.warning(st.session_state.reqwf_refiner_output)
            if st.session_state.reqwf_current_step == 3 and st.button("Continuar a Edición ➔"):
                st.session_state.reqwf_current_step = 4
                st.rerun()

    if st.session_state.reqwf_current_step >= 4:
        step_header("Paso 4: Agent 03 - Editor Use Case")
        if not st.session_state.reqwf_editor_output:
            input_editor = (
                f"Contexto original:\n{base_context}\n\n"
                f"Output del refiner:\n{st.session_state.reqwf_refiner_output}"
            )
            st.session_state.reqwf_editor_output = _run_agent(
                "Agent_Requirement_WorkFlow_03_Editor_Use_Case.md",
                input_editor,
            )

        st.session_state.reqwf_editor_output = st.text_area(
            "Historia editada (puede ajustarla manualmente)",
            value=st.session_state.reqwf_editor_output,
            height=280,
        )

        if st.session_state.reqwf_current_step == 4 and st.button("Aprobar historia y generar diagrama ➔"):
            st.session_state.reqwf_current_step = 5
            st.rerun()

    if st.session_state.reqwf_current_step >= 5:
        step_header("Paso 5: Agent 04 - Diagram Use Case")
        if not st.session_state.reqwf_diagram_output:
            st.session_state.reqwf_diagram_output = _run_agent(
                "Agent_Requirement_WorkFlow_04_Diagram_Use_Case.md",
                st.session_state.reqwf_editor_output,
            )

        st.markdown(st.session_state.reqwf_diagram_output)

        if st.session_state.reqwf_current_step == 5 and st.button("Continuar a sizing técnico ➔"):
            st.session_state.reqwf_current_step = 6
            st.rerun()

    if st.session_state.reqwf_current_step >= 6:
        step_header("Paso 6: Agent 05 - Sizer")
        if not st.session_state.reqwf_sizer_output:
            st.session_state.reqwf_sizer_output = _run_agent(
                "Agent_Requirement_WorkFlow_05_Sizer.md",
                st.session_state.reqwf_editor_output,
            )

        st.info(st.session_state.reqwf_sizer_output)

        if st.session_state.reqwf_current_step == 6 and st.button("Continuar a plan de pruebas ➔"):
            st.session_state.reqwf_current_step = 7
            st.rerun()

    if st.session_state.reqwf_current_step >= 7:
        step_header("Paso 7: Agent 06 - Generator Test Case")
        if not st.session_state.reqwf_qa_output:
            input_qa = (
                f"Historia refinada:\n{st.session_state.reqwf_editor_output}\n\n"
                f"Sizing:\n{st.session_state.reqwf_sizer_output}"
            )
            st.session_state.reqwf_qa_output = _run_agent(
                "Agent_Requirement_WorkFlow_06_Generator_Test_Case.md",
                input_qa,
            )

        st.success(st.session_state.reqwf_qa_output)

        if st.session_state.reqwf_current_step == 7 and st.button("Consolidar issue final ➔"):
            st.session_state.reqwf_current_step = 8
            st.rerun()

    if st.session_state.reqwf_current_step >= 8:
        step_header("Paso 8: Agent 07 - Issue Formatter")
        if not st.session_state.reqwf_issue_output:
            final_context = (
                f"## Input original\n{base_context}\n\n"
                f"## Historia editada\n{st.session_state.reqwf_editor_output}\n\n"
                f"## Diagrama\n{st.session_state.reqwf_diagram_output}\n\n"
                f"## Sizing\n{st.session_state.reqwf_sizer_output}\n\n"
                f"## QA\n{st.session_state.reqwf_qa_output}"
            )
            st.session_state.reqwf_issue_output = _run_agent(
                "Agent_Requirement_WorkFlow_07_issue_formatter.md",
                final_context,
            )

        st.markdown(st.session_state.reqwf_issue_output)

        st.download_button(
            "📥 Descargar ticket final (Markdown)",
            st.session_state.reqwf_issue_output,
            file_name="requirement_workflow_issue.md",
            mime="text/markdown",
        )

        if st.button("🔄 Nuevo Requirement Workflow"):
            for key, default_value in state_keys.items():
                st.session_state[f"reqwf_{key}"] = default_value
            st.rerun()