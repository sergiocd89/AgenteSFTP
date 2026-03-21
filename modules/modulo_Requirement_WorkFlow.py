from io import BytesIO

import streamlit as st
import streamlit.components.v1 as components
from core.utils import call_llm, load_agent_prompt, step_header


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


def _extract_mermaid_code(markdown_text: str) -> str:
    """Extrae el primer bloque ```mermaid ... ``` del texto del agente."""
    if not markdown_text:
        return ""

    marker = "```mermaid"
    start = markdown_text.find(marker)
    if start == -1:
        return ""

    content_start = start + len(marker)
    end = markdown_text.find("```", content_start)
    if end == -1:
        return ""

    return markdown_text[content_start:end].strip()


def _render_mermaid(mermaid_code: str) -> None:
    """Renderiza Mermaid como SVG en Streamlit usando componentes HTML."""
    html = f"""
    <div id=\"mermaid-container\">{mermaid_code}</div>
    <script type=\"module\">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
        const container = document.querySelector('#mermaid-container');
        container.classList.add('mermaid');
        mermaid.run({{ querySelector: '#mermaid-container' }});
    </script>
    <style>
        #mermaid-container {{
            display: flex;
            justify-content: center;
            width: 100%;
            overflow-x: auto;
            padding: 12px;
            background: #ffffff;
            border-radius: 8px;
        }}
        #mermaid-container svg {{
            max-width: 100%;
            height: auto;
        }}
    </style>
    """
    components.html(html, height=520, scrolling=True)


def _remove_mermaid_blocks(markdown_text: str) -> str:
    """Elimina bloques ```mermaid``` para no mostrarlos como código."""
    if not markdown_text:
        return ""

    cleaned = markdown_text
    marker = "```mermaid"
    while True:
        start = cleaned.find(marker)
        if start == -1:
            break
        end = cleaned.find("```", start + len(marker))
        if end == -1:
            break
        cleaned = cleaned[:start] + cleaned[end + 3:]

    return cleaned.strip()


def _markdown_to_plain_lines(markdown_text: str) -> list[str]:
    """Reduce markdown a líneas legibles para exportación simple a PDF."""
    if not markdown_text:
        return []

    cleaned_text = _remove_mermaid_blocks(markdown_text)
    replacements = {
        "### ": "",
        "## ": "",
        "# ": "",
        "**": "",
        "`": "",
        "- [ ] ": "[ ] ",
        "- ": "• ",
    }

    for old_value, new_value in replacements.items():
        cleaned_text = cleaned_text.replace(old_value, new_value)

    return [line.strip() for line in cleaned_text.splitlines() if line.strip()]


def _build_pdf_bytes(title: str, markdown_text: str) -> bytes:
    """Genera un PDF básico a partir del markdown final del issue."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    for line in _markdown_to_plain_lines(markdown_text):
        safe_line = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        story.append(Paragraph(safe_line, styles["BodyText"]))
        story.append(Spacer(1, 8))

    document.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def show_requirement_workflow():
    st.title("🧩 Requirement Workflow")
    st.caption("Pipeline agéntico para convertir requerimientos en un ticket listo para Jira/GitHub.")

    state_keys = {
        "current_step": 1,
        "requirement_text": "",
        "documents_context": "",
        "loaded_documents": [],
        "refactor_decision": "Sí",
        "refactor_feedback": "",
        "refactor_history": [],
        "creator_output": "",
        "refiner_output": "",
        "refined_output": "",
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
        st.text_area(
            "Requerimiento ingresado (solo lectura)",
            value=st.session_state.reqwf_requirement_text,
            height=200,
            disabled=True,
        )
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
            current_story = st.session_state.reqwf_refined_output or st.session_state.reqwf_creator_output
            st.info(current_story)

            if st.session_state.reqwf_refactor_history:
                with st.expander(f"📋 Historial de refactorizaciones ({len(st.session_state.reqwf_refactor_history)})", expanded=False):
                    for idx, entry in enumerate(st.session_state.reqwf_refactor_history, start=1):
                        st.markdown(f"**Refactorización {idx}:**")
                        st.text(entry)
                        if idx < len(st.session_state.reqwf_refactor_history):
                            st.divider()

            st.session_state.reqwf_refactor_decision = st.radio(
                "¿Desea refactorizar la historia de usuario generada?",
                options=["Sí", "No"],
                horizontal=True,
                index=0 if st.session_state.reqwf_refactor_decision == "Sí" else 1,
            )

            if st.session_state.reqwf_refactor_decision == "Sí":
                st.session_state.reqwf_refactor_feedback = st.text_area(
                    "Ingrese qué desea corregir o mejorar en la historia",
                    value=st.session_state.reqwf_refactor_feedback,
                    height=140,
                    placeholder="Ejemplo: Agregar casos de error, aclarar reglas de negocio y mejorar criterios de aceptación.",
                )
            else:
                st.session_state.reqwf_refactor_feedback = ""

            if st.session_state.reqwf_refactor_decision == "Sí":
                if st.button("Aplicar refactorización ➔", disabled=not st.session_state.reqwf_refactor_feedback.strip()):
                    input_refiner = (
                        f"Contexto original:\n{base_context}\n\n"
                        f"Historia inicial:\n{current_story}\n\n"
                        f"Correcciones solicitadas por el usuario:\n"
                        f"{st.session_state.reqwf_refactor_feedback or 'Sin observaciones adicionales.'}"
                    )
                    st.session_state.reqwf_refiner_output = _run_agent(
                        "Agent_Requirement_WorkFlow_02_Refiner_Use_Case.md",
                        input_refiner,
                    )
                    st.session_state.reqwf_refined_output = st.session_state.reqwf_refiner_output
                    st.session_state.reqwf_refactor_history.append(
                        st.session_state.reqwf_refactor_feedback
                    )
                    st.session_state.reqwf_refactor_feedback = ""
                    st.rerun()
            elif st.button("Continuar sin más refactorización ➔"):
                st.session_state.reqwf_current_step = 3
                st.rerun()

    if st.session_state.reqwf_current_step >= 3:
        step_header("Paso 3: Agent 04 - Diagram Use Case")
        if not st.session_state.reqwf_diagram_output:
            st.session_state.reqwf_diagram_output = _run_agent(
                "Agent_Requirement_WorkFlow_04_Diagram_Use_Case.md",
                st.session_state.reqwf_refined_output,
            )

        mermaid_code = _extract_mermaid_code(st.session_state.reqwf_diagram_output)
        if mermaid_code:
            st.markdown("#### Diagrama visual")
            _render_mermaid(mermaid_code)
        else:
            st.warning("No se encontró un bloque Mermaid en la respuesta del agente. Mostrando salida textual.")
            st.markdown(st.session_state.reqwf_diagram_output)

        if st.session_state.reqwf_current_step == 3 and st.button("Continuar a sizing técnico ➔"):
            st.session_state.reqwf_current_step = 4
            st.rerun()

    if st.session_state.reqwf_current_step >= 4:
        step_header("Paso 4: Agent 05 - Sizer")
        if not st.session_state.reqwf_sizer_output:
            st.session_state.reqwf_sizer_output = _run_agent(
                "Agent_Requirement_WorkFlow_05_Sizer.md",
                st.session_state.reqwf_refined_output,
            )

        st.info(st.session_state.reqwf_sizer_output)

        if st.session_state.reqwf_current_step == 4 and st.button("Continuar a plan de pruebas ➔"):
            st.session_state.reqwf_current_step = 5
            st.rerun()

    if st.session_state.reqwf_current_step >= 5:
        step_header("Paso 5: Agent 06 - Generator Test Case")
        if not st.session_state.reqwf_qa_output:
            input_qa = (
                f"Historia refinada:\n{st.session_state.reqwf_refined_output}\n\n"
                f"Sizing:\n{st.session_state.reqwf_sizer_output}"
            )
            st.session_state.reqwf_qa_output = _run_agent(
                "Agent_Requirement_WorkFlow_06_Generator_Test_Case.md",
                input_qa,
            )

        st.success(st.session_state.reqwf_qa_output)

        if st.session_state.reqwf_current_step == 5 and st.button("Consolidar issue final ➔"):
            st.session_state.reqwf_current_step = 6
            st.rerun()

    if st.session_state.reqwf_current_step >= 6:
        step_header("Paso 6: Agent 07 - Issue Formatter")
        if not st.session_state.reqwf_issue_output:
            final_context = (
                f"## Input original\n{base_context}\n\n"
                f"## Historia refinada\n{st.session_state.reqwf_refined_output}\n\n"
                f"## Diagrama\n{st.session_state.reqwf_diagram_output}\n\n"
                f"## Sizing\n{st.session_state.reqwf_sizer_output}\n\n"
                f"## QA\n{st.session_state.reqwf_qa_output}"
            )
            st.session_state.reqwf_issue_output = _run_agent(
                "Agent_Requirement_WorkFlow_07_issue_formatter.md",
                final_context,
            )

        issue_mermaid_code = _extract_mermaid_code(st.session_state.reqwf_issue_output)
        if issue_mermaid_code:
            st.markdown("#### Diagrama visual del issue")
            _render_mermaid(issue_mermaid_code)

        issue_markdown_clean = _remove_mermaid_blocks(st.session_state.reqwf_issue_output)
        st.markdown(issue_markdown_clean)

        pdf_bytes = _build_pdf_bytes(
            "Requirement Workflow Issue",
            st.session_state.reqwf_issue_output,
        )

        st.download_button(
            "📥 Descargar ticket final (Markdown)",
            st.session_state.reqwf_issue_output,
            file_name="requirement_workflow_issue.md",
            mime="text/markdown",
        )

        st.download_button(
            "📄 Descargar ticket final (PDF)",
            pdf_bytes,
            file_name="requirement_workflow_issue.pdf",
            mime="application/pdf",
        )

        if st.button("🔄 Nuevo Requirement Workflow"):
            for key, default_value in state_keys.items():
                st.session_state[f"reqwf_{key}"] = default_value
            st.rerun()