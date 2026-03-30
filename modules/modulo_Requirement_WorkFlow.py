from io import BytesIO
import os
import re
import time

import streamlit as st
import streamlit.components.v1 as components
from core.domain.integration_service import publish_jira_issue, resolve_confluence_metadata
from core.infrastructure import backend_api_client
from core.login import run_backend_operation_with_retry
from core.logger import get_logger, log_operation
from core.observability import (
    format_message_with_request_id,
    format_workflow_log_details,
    generate_request_id,
)
from core.ui.ai_presenter import run_llm_text
from core.utils import load_agent_prompt, step_header


LOGGER = get_logger(__name__)


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
    requirement_step_map = {
        "Agent_Requirement_WorkFlow_01_Creator_Use_Case.md": "create",
        "Agent_Requirement_WorkFlow_02_Refiner_Use_Case.md": "refine",
        "Agent_Requirement_WorkFlow_04_Diagram_Use_Case.md": "diagram",
        "Agent_Requirement_WorkFlow_05_Sizer.md": "size",
        "Agent_Requirement_WorkFlow_06_Generator_Test_Case.md": "test_cases",
        "Agent_Requirement_WorkFlow_07_issue_formatter.md": "format_issue",
    }

    step = requirement_step_map.get(agent_filename)
    if step and backend_api_client.is_backend_enabled() and st.session_state.get("backend_access_token"):
        request_id = generate_request_id()
        started_at = time.perf_counter()
        ok, payload = run_backend_operation_with_retry(
            lambda token: backend_api_client.execute_workflow_step(
                token=token,
                workflow="requirement",
                step=step,
                source_input=user_content,
                context="",
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
            details=format_workflow_log_details(request_id, "requirement", step, duration_ms),
        )
        if ok and isinstance(payload, dict):
            return str(payload.get("content") or "No se pudo obtener respuesta del backend en este paso.")

    sys_role = load_agent_prompt(agent_filename)
    result = run_llm_text(
        sys_role,
        user_content,
        st.session_state.model_name,
        st.session_state.temp,
    )
    return result or "No se pudo obtener respuesta del modelo en este paso."


def _split_user_stories(refined_text: str) -> list[str]:
    """Separa historias de usuario en bloques para diagramarlas individualmente."""
    if not refined_text or not refined_text.strip():
        return []

    normalized = refined_text.strip()
    # Regla principal: cada historia inicia con [US-00N], por ejemplo [US-001].
    us_marker_pattern = re.compile(r"\[US-\d+\]", re.IGNORECASE)
    matches = list(us_marker_pattern.finditer(normalized))
    if len(matches) <= 1:
        return [normalized]

    chunks: list[str] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

    return chunks or [normalized]


def _extract_story_title(story_text: str, index: int) -> str:
    """Obtiene un titulo legible para cada historia de usuario."""
    if not story_text or not story_text.strip():
        return f"Historia {index}"

    for raw_line in story_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Elimina marcadores markdown comunes para usar el texto como titulo.
        line = re.sub(r"^[#\-\*\d\.\)\s]+", "", line).strip()
        if line:
            return line[:120]

    return f"Historia {index}"


def _build_diagram_output(diagrams: list[str]) -> str:
    """Consolida salida de diagramas para uso en Jira/issue final."""
    return "\n\n---\n\n".join(
        [
            f"### Diagrama Historia {idx}\n{diagram}"
            for idx, diagram in enumerate(diagrams, start=1)
        ]
    )


def _build_sizer_output(sizers: list[str]) -> str:
    """Consolida salida de dimensionamiento para pasos posteriores."""
    return "\n\n---\n\n".join(
        [
            f"### Sizing Historia {idx}\n{sizer}"
            for idx, sizer in enumerate(sizers, start=1)
        ]
    )


def _build_qa_output(qa_items: list[str]) -> str:
    """Consolida salida de casos de prueba para pasos posteriores."""
    return "\n\n---\n\n".join(
        [
            f"### QA Historia {idx}\n{qa_text}"
            for idx, qa_text in enumerate(qa_items, start=1)
        ]
    )


def _resolve_story_blocks_from_source(story_source: str) -> tuple[list[str], list[str]]:
    """Construye historias y títulos desde una fuente textual para reutilizar en Jira."""
    story_blocks = _split_user_stories(story_source)
    if not story_blocks and story_source:
        story_blocks = [story_source]

    cleaned_blocks = [story.strip() for story in story_blocks if story and story.strip()]
    story_titles = [_extract_story_title(story, idx) for idx, story in enumerate(cleaned_blocks, start=1)]
    return cleaned_blocks, story_titles


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
        "confluence_link": "",
        "confluence_user": "",
        "confluence_password": "",
        "confluence_space_key": "",
        "confluence_parent_id": "",
        "confluence_page_title": "",
        "confluence_page_id": "",
        "refactor_decision": "Sí",
        "refactor_feedback": "",
        "refactor_history": [],
        "creator_output": "",
        "refiner_output": "",
        "refined_output": "",
        "diagram_output": "",
        "diagram_outputs": [],
        "skip_diagram_step": False,
        "story_blocks": [],
        "story_titles": [],
        "diagram_source_signature": "",
        "jira_base_url": os.getenv("JIRA_BASE_URL", ""),
        "jira_project_key": os.getenv("JIRA_PROJECT_KEY", ""),
        "jira_issue_type": os.getenv("JIRA_ISSUE_TYPE", "Story"),
        "jira_user": os.getenv("JIRA_USER", ""),
        "jira_password": os.getenv("JIRA_PASSWORD", ""),
        "jira_last_result": "",
        "sizer_outputs": [],
        "sizer_source_signature": "",
        "sizer_output": "",
        "qa_outputs": [],
        "qa_source_signature": "",
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
                "Ingrese la información base (texto libre)",
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

            st.markdown("#### Referencia desde Confluence (opcional)")
            # Fila 3: usuario + password/token
            col_user, col_token = st.columns(2)
            with col_user:
                confluence_user = st.text_input(
                    "Usuario Confluence",
                    value=st.session_state.reqwf_confluence_user,
                    placeholder="usuario@empresa.com",
                )
            with col_token:
                confluence_password = st.text_input(
                    "Contraseña / API Token Confluence",
                    value=st.session_state.reqwf_confluence_password,
                    type="password",
                )
            confluence_link = st.text_input(
                "Link de Confluence",
                value=st.session_state.reqwf_confluence_link,
                placeholder="https://tuempresa.atlassian.net/wiki/pages/viewpage.action?pageId=12345",
            )
            if st.button("Identificar space y parent ID desde link", use_container_width=True):
                if not (confluence_link.strip() and confluence_user.strip() and confluence_password.strip()):
                    st.warning("Completa link, usuario y contraseña/token para consultar Confluence.")
                else:
                    if backend_api_client.is_backend_enabled() and st.session_state.get("backend_access_token"):
                        request_id = generate_request_id()
                        ok, payload = run_backend_operation_with_retry(
                            lambda token: backend_api_client.get_confluence_metadata(
                                token,
                                confluence_link.strip(),
                                confluence_user.strip(),
                                confluence_password.strip(),
                            )
                        )
                        result_meta = payload if isinstance(payload, dict) else {"success": False, "message": str(payload)}
                        if ok:
                            result_meta["success"] = True
                        else:
                            result_meta["message"] = format_message_with_request_id(
                                str(result_meta.get("message", "No se pudo consultar Confluence.")),
                                request_id,
                            )
                    else:
                        result_meta = resolve_confluence_metadata(
                            confluence_link.strip(),
                            confluence_user.strip(),
                            confluence_password.strip(),
                        )
                    if result_meta.get("success"):
                        metadata = result_meta.get("data") or {}
                        st.session_state.reqwf_confluence_link = confluence_link.strip()
                        st.session_state.reqwf_confluence_user = confluence_user.strip()
                        st.session_state.reqwf_confluence_password = confluence_password.strip()
                        st.session_state.reqwf_confluence_space_key = metadata.get("space_key", "")
                        st.session_state.reqwf_confluence_parent_id = metadata.get("parent_id", "")
                        st.session_state.reqwf_confluence_page_title = metadata.get("title", "")
                        st.session_state.reqwf_confluence_page_id = metadata.get("page_id", "")
                        st.success(
                            "Confluence identificado. "
                            f"Space: {st.session_state.reqwf_confluence_space_key or 'N/D'} | "
                            f"Parent ID: {st.session_state.reqwf_confluence_parent_id or 'N/D'}"
                        )
                    else:
                        st.error(result_meta.get("message", "No se pudo consultar Confluence."))

            if st.session_state.reqwf_confluence_space_key or st.session_state.reqwf_confluence_parent_id:
                st.caption(
                    "Confluence detectado - "
                    f"Space: {st.session_state.reqwf_confluence_space_key or 'N/D'} | "
                    f"Parent ID: {st.session_state.reqwf_confluence_parent_id or 'N/D'}"
                )

            if st.button("Iniciar Workflow ➔", use_container_width=True, type="primary"):
                if not requirement_text.strip():
                    st.warning("Debe ingresar un requerimiento antes de continuar.")
                else:
                    docs_context, loaded_docs = _build_documents_context(uploaded_files)
                    st.session_state.reqwf_requirement_text = requirement_text.strip()
                    st.session_state.reqwf_documents_context = docs_context
                    st.session_state.reqwf_loaded_documents = loaded_docs
                    st.session_state.reqwf_confluence_link = confluence_link.strip()
                    st.session_state.reqwf_confluence_user = confluence_user.strip()
                    st.session_state.reqwf_confluence_password = confluence_password.strip()

                    if (
                        confluence_link.strip()
                        and confluence_user.strip()
                        and confluence_password.strip()
                        and not st.session_state.reqwf_confluence_space_key
                    ):
                        if backend_api_client.is_backend_enabled() and st.session_state.get("backend_access_token"):
                            request_id = generate_request_id()
                            ok, payload = run_backend_operation_with_retry(
                                lambda token: backend_api_client.get_confluence_metadata(
                                    token,
                                    confluence_link.strip(),
                                    confluence_user.strip(),
                                    confluence_password.strip(),
                                )
                            )
                            result_meta = payload if isinstance(payload, dict) else {"success": False, "message": str(payload)}
                            if ok:
                                result_meta["success"] = True
                            else:
                                result_meta["message"] = format_message_with_request_id(
                                    str(result_meta.get("message", "No se pudo consultar Confluence.")),
                                    request_id,
                                )
                        else:
                            result_meta = resolve_confluence_metadata(
                                confluence_link.strip(),
                                confluence_user.strip(),
                                confluence_password.strip(),
                            )
                        if result_meta.get("success"):
                            metadata = result_meta.get("data") or {}
                            st.session_state.reqwf_confluence_space_key = metadata.get("space_key", "")
                            st.session_state.reqwf_confluence_parent_id = metadata.get("parent_id", "")
                            st.session_state.reqwf_confluence_page_title = metadata.get("title", "")
                            st.session_state.reqwf_confluence_page_id = metadata.get("page_id", "")
                        else:
                            st.warning(
                                "No se pudo resolver metadata de Confluence: "
                                f"{result_meta.get('message', 'error no especificado')}"
                            )

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
        f"{st.session_state.reqwf_documents_context or 'No se adjuntaron documentos.'}\n\n"
        "## Contexto Confluence\n"
        f"Link: {st.session_state.reqwf_confluence_link or 'No informado'}\n"
        f"Space Key: {st.session_state.reqwf_confluence_space_key or 'No identificado'}\n"
        f"Parent ID: {st.session_state.reqwf_confluence_parent_id or 'No identificado'}\n"
        f"Page ID: {st.session_state.reqwf_confluence_page_id or 'No identificado'}\n"
        f"Titulo pagina: {st.session_state.reqwf_confluence_page_title or 'No identificado'}"
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
            else:
                col_continue, col_skip = st.columns(2)
                with col_continue:
                    if st.button("Continuar sin más refactorización ➔", use_container_width=True):
                        st.session_state.reqwf_skip_diagram_step = False
                        st.session_state.reqwf_current_step = 3
                        st.rerun()
                with col_skip:
                    if st.button("Saltar Paso 3 (sin diagramas) ➔", use_container_width=True):
                        story_source_skip = (
                            st.session_state.reqwf_refined_output
                            or st.session_state.reqwf_creator_output
                            or st.session_state.reqwf_requirement_text
                        )
                        skip_blocks, skip_titles = _resolve_story_blocks_from_source(story_source_skip)
                        st.session_state.reqwf_story_blocks = skip_blocks
                        st.session_state.reqwf_story_titles = skip_titles
                        st.session_state.reqwf_diagram_outputs = []
                        st.session_state.reqwf_diagram_output = "Diagramas omitidos por decisión del usuario en Paso 2."
                        st.session_state.reqwf_diagram_source_signature = ""
                        st.session_state.reqwf_skip_diagram_step = True
                        st.session_state.reqwf_current_step = 4
                        st.rerun()

    if st.session_state.reqwf_current_step >= 3 and not st.session_state.reqwf_skip_diagram_step:
        step_header("Paso 3: Agent 04 - Diagram Use Case")
        story_source = (
            st.session_state.reqwf_refined_output
            or st.session_state.reqwf_creator_output
            or st.session_state.reqwf_requirement_text
        )
        source_signature = str(hash(story_source)) if story_source else ""

        needs_regeneration = (
            not st.session_state.reqwf_diagram_outputs
            or st.session_state.reqwf_diagram_source_signature != source_signature
        )

        if needs_regeneration:
            story_blocks = _split_user_stories(story_source)
            if not story_blocks:
                story_blocks = [story_source] if story_source else []

            diagrams: list[str] = []
            kept_story_blocks: list[str] = []
            story_titles: list[str] = []
            for idx, story in enumerate(story_blocks, start=1):
                if not story or not story.strip():
                    continue
                diagram = _run_agent(
                    "Agent_Requirement_WorkFlow_04_Diagram_Use_Case.md",
                    story,
                )
                diagrams.append(diagram)
                kept_story_blocks.append(story)
                story_titles.append(_extract_story_title(story, idx))

            if not diagrams and story_source:
                diagrams.append(
                    _run_agent(
                        "Agent_Requirement_WorkFlow_04_Diagram_Use_Case.md",
                        story_source,
                    )
                )
                kept_story_blocks.append(story_source)
                story_titles.append(_extract_story_title(story_source, 1))

            st.session_state.reqwf_diagram_outputs = diagrams
            st.session_state.reqwf_story_blocks = kept_story_blocks
            st.session_state.reqwf_story_titles = story_titles
            st.session_state.reqwf_diagram_source_signature = source_signature
            st.session_state.reqwf_diagram_output = _build_diagram_output(diagrams)

        if not st.session_state.reqwf_diagram_outputs:
            st.warning(
                "No se pudo generar un diagrama en este paso. Revisa la historia refinada o vuelve a generar el paso 2."
            )
        else:
            for idx, diagram_output in enumerate(st.session_state.reqwf_diagram_outputs, start=1):
                story_title = (
                    st.session_state.reqwf_story_titles[idx - 1]
                    if idx - 1 < len(st.session_state.reqwf_story_titles)
                    else f"Historia {idx}"
                )
                st.markdown(f"#### {story_title}")
                mermaid_code = _extract_mermaid_code(diagram_output)
                if mermaid_code:
                    _render_mermaid(mermaid_code)
                else:
                    st.warning(
                        f"No se encontró un bloque Mermaid para la historia {idx}. Mostrando salida textual."
                    )
                    st.markdown(diagram_output)

                if st.button("Reinterpretar diagrama", key=f"reqwf_btn_reinterpret_{idx}"):
                    story_input = (
                        st.session_state.reqwf_story_blocks[idx - 1]
                        if idx - 1 < len(st.session_state.reqwf_story_blocks)
                        else story_source
                    )
                    regenerated = _run_agent(
                        "Agent_Requirement_WorkFlow_04_Diagram_Use_Case.md",
                        story_input,
                    )
                    st.session_state.reqwf_diagram_outputs[idx - 1] = regenerated
                    st.session_state.reqwf_diagram_output = _build_diagram_output(
                        st.session_state.reqwf_diagram_outputs
                    )
                    st.rerun()

        if st.session_state.reqwf_current_step == 3 and st.button("Continuar a publicación Jira ➔"):
            st.session_state.reqwf_current_step = 4
            st.rerun()
    elif st.session_state.reqwf_current_step >= 4 and st.session_state.reqwf_skip_diagram_step:
        step_header("Paso 3: Agent 04 - Diagram Use Case")
        st.info("Paso 3 omitido. Puedes continuar con la publicación en Jira sin diagramas.")

    if st.session_state.reqwf_current_step >= 4:
        step_header("Paso 4: Publicación en Jira")
        if st.session_state.reqwf_skip_diagram_step:
            st.caption("Completa los datos de Jira para publicar historias sin diagramas.")
        else:
            st.caption("Completa los datos de Jira para publicar todas las historias con su diagrama.")

        # Fila 1: URL Jira completa
        st.session_state.reqwf_jira_base_url = st.text_input(
            "Jira Base URL",
            value=st.session_state.reqwf_jira_base_url,
            placeholder="https://tuempresa.atlassian.net",
        ).strip()

        # Fila 2: Project Key + Issue Type
        col_project, col_issue_type = st.columns(2)
        with col_project:
            st.session_state.reqwf_jira_project_key = st.text_input(
                "Project Key",
                value=st.session_state.reqwf_jira_project_key,
                placeholder="PROJ",
            ).strip().upper()
        with col_issue_type:
            st.session_state.reqwf_jira_issue_type = st.selectbox(
                "Issue Type",
                ["Story", "Task", "Bug", "Epic"],
                index=["Story", "Task", "Bug", "Epic"].index(
                    st.session_state.reqwf_jira_issue_type
                    if st.session_state.reqwf_jira_issue_type in ["Story", "Task", "Bug", "Epic"]
                    else "Story"
                ),
            )

        # Fila 3: JIRA_USER + JIRA_PASSWORD
        col_user, col_password = st.columns(2)
        with col_user:
            st.session_state.reqwf_jira_user = st.text_input(
                "JIRA_USER",
                value=st.session_state.reqwf_jira_user,
                placeholder="usuario@empresa.com",
            ).strip()
        with col_password:
            st.session_state.reqwf_jira_password = st.text_input(
                "JIRA_PASSWORD",
                value=st.session_state.reqwf_jira_password,
                type="password",
                placeholder="API token / password",
            ).strip()

        total_histories = len(st.session_state.reqwf_story_blocks)
        st.caption(f"Se publicarán {total_histories} historias usando el mismo Project Key.")

        if st.button("Crear Issues en Jira (1 por historia)", use_container_width=True, key="reqwf_btn_create_jira"):
            jira_base_url = st.session_state.reqwf_jira_base_url.strip()
            jira_project_key = st.session_state.reqwf_jira_project_key.strip().upper()
            jira_issue_type = st.session_state.reqwf_jira_issue_type.strip()
            jira_user = st.session_state.reqwf_jira_user.strip()
            jira_password = st.session_state.reqwf_jira_password.strip()

            if not st.session_state.reqwf_story_blocks:
                st.session_state.reqwf_jira_last_result = "No hay historias para publicar en Jira."
                st.error(st.session_state.reqwf_jira_last_result)
            elif not jira_base_url or not jira_project_key or not jira_issue_type:
                st.session_state.reqwf_jira_last_result = (
                    "Completa Jira Base URL, Project Key e Issue Type antes de publicar."
                )
                st.error(st.session_state.reqwf_jira_last_result)
            elif not jira_user or not jira_password:
                st.session_state.reqwf_jira_last_result = (
                    "Completa JIRA_USER y JIRA_PASSWORD antes de publicar."
                )
                st.error(st.session_state.reqwf_jira_last_result)
            elif not re.match(r"^https?://", jira_base_url, flags=re.IGNORECASE):
                st.session_state.reqwf_jira_last_result = (
                    "Jira Base URL debe iniciar con http:// o https://."
                )
                st.error(st.session_state.reqwf_jira_last_result)
            else:
                ok_count = 0
                errors: list[str] = []
                created: list[str] = []

                for idx, story in enumerate(st.session_state.reqwf_story_blocks, start=1):
                    title = (
                        st.session_state.reqwf_story_titles[idx - 1]
                        if idx - 1 < len(st.session_state.reqwf_story_titles)
                        else f"Historia {idx}"
                    )
                    summary = f"[US-{idx:03d}] {title}"[:255]
                    diagram_text = (
                        st.session_state.reqwf_diagram_outputs[idx - 1]
                        if idx - 1 < len(st.session_state.reqwf_diagram_outputs)
                        else "Sin diagrama disponible para esta historia."
                    )
                    jira_description = (
                        f"Historia de Usuario {idx}:\n"
                        f"{story}\n\n"
                        "Diagrama asociado:\n"
                        f"{diagram_text}"
                    )

                    if backend_api_client.is_backend_enabled() and st.session_state.get("backend_access_token"):
                        request_id = generate_request_id()
                        ok, payload = run_backend_operation_with_retry(
                            lambda token: backend_api_client.create_jira_issue(
                                token,
                                jira_base_url,
                                jira_project_key,
                                jira_issue_type,
                                summary,
                                jira_description,
                                jira_user,
                                jira_password,
                            )
                        )
                        result = payload if isinstance(payload, dict) else {"success": False, "message": str(payload)}
                        if ok:
                            result["success"] = True
                        else:
                            result["message"] = format_message_with_request_id(
                                str(result.get("message", "Error al crear issue en Jira.")),
                                request_id,
                            )
                    else:
                        result = publish_jira_issue(
                            jira_base_url,
                            jira_project_key,
                            jira_issue_type,
                            summary,
                            jira_description,
                            jira_user,
                            jira_password,
                        )

                    if result.get("success"):
                        ok_count += 1
                        created.append(result.get("message", "Issue creado."))
                    else:
                        errors.append(
                            f"Historia {idx}: {result.get('message', 'Error al crear issue en Jira.')}"
                        )

                result_lines = [
                    f"Publicación finalizada. Issues creados: {ok_count}/{len(st.session_state.reqwf_story_blocks)}."
                ]
                if created:
                    result_lines.extend(created)
                if errors:
                    result_lines.extend(errors)

                st.session_state.reqwf_jira_last_result = "\n".join(result_lines)

                if errors:
                    st.error(st.session_state.reqwf_jira_last_result)
                else:
                    st.success(st.session_state.reqwf_jira_last_result)

        if st.session_state.reqwf_jira_last_result and not st.session_state.reqwf_jira_last_result.startswith("Issue creado"):
            st.caption("Último resultado Jira: " + st.session_state.reqwf_jira_last_result)

        if st.session_state.reqwf_current_step == 4 and st.button("Omitir Jira y continuar ➔"):
            st.session_state.reqwf_current_step = 5
            st.rerun()

        if st.session_state.reqwf_current_step == 4 and st.button("Continuar a sizing técnico ➔"):
            st.session_state.reqwf_current_step = 5
            st.rerun()

    if st.session_state.reqwf_current_step >= 5:
        step_header("Paso 5: Agent 05 - Sizer")
        sizer_story_blocks = st.session_state.reqwf_story_blocks or []
        if not sizer_story_blocks:
            fallback_story = (
                st.session_state.reqwf_refined_output
                or st.session_state.reqwf_creator_output
                or st.session_state.reqwf_requirement_text
            )
            sizer_story_blocks = [fallback_story] if fallback_story else []

        sizer_signature = str(hash("\n\n".join(sizer_story_blocks))) if sizer_story_blocks else ""
        needs_sizer_regeneration = (
            not st.session_state.reqwf_sizer_outputs
            or st.session_state.reqwf_sizer_source_signature != sizer_signature
        )

        if needs_sizer_regeneration:
            sizers: list[str] = []
            for story in sizer_story_blocks:
                if not story or not story.strip():
                    continue
                sizers.append(
                    _run_agent(
                        "Agent_Requirement_WorkFlow_05_Sizer.md",
                        story,
                    )
                )

            st.session_state.reqwf_sizer_outputs = sizers
            st.session_state.reqwf_sizer_source_signature = sizer_signature
            st.session_state.reqwf_sizer_output = _build_sizer_output(sizers)

        if not st.session_state.reqwf_sizer_outputs:
            st.warning("No se pudo generar dimensionamiento para las historias disponibles.")
        else:
            for idx, sizer_text in enumerate(st.session_state.reqwf_sizer_outputs, start=1):
                story_title = (
                    st.session_state.reqwf_story_titles[idx - 1]
                    if idx - 1 < len(st.session_state.reqwf_story_titles)
                    else f"Historia {idx}"
                )
                st.markdown(f"#### Dimensionamiento - {story_title}")
                st.info(sizer_text)

        if st.session_state.reqwf_current_step == 5 and st.button("Continuar a plan de pruebas ➔"):
            st.session_state.reqwf_current_step = 6
            st.rerun()

    if st.session_state.reqwf_current_step >= 6:
        step_header("Paso 6: Agent 06 - Generator Test Case")
        qa_story_blocks = st.session_state.reqwf_story_blocks or []
        if not qa_story_blocks:
            fallback_story = (
                st.session_state.reqwf_refined_output
                or st.session_state.reqwf_creator_output
                or st.session_state.reqwf_requirement_text
            )
            qa_story_blocks = [fallback_story] if fallback_story else []

        qa_signature = str(hash(
            "\n\n".join(qa_story_blocks)
            + "\n\n"
            + "\n\n".join(st.session_state.reqwf_sizer_outputs)
        )) if qa_story_blocks else ""

        needs_qa_regeneration = (
            not st.session_state.reqwf_qa_outputs
            or st.session_state.reqwf_qa_source_signature != qa_signature
        )

        if needs_qa_regeneration:
            qa_items: list[str] = []
            for idx, story in enumerate(qa_story_blocks, start=1):
                if not story or not story.strip():
                    continue

                story_sizing = (
                    st.session_state.reqwf_sizer_outputs[idx - 1]
                    if idx - 1 < len(st.session_state.reqwf_sizer_outputs)
                    else st.session_state.reqwf_sizer_output
                )
                input_qa = (
                    f"Historia de usuario {idx}:\n{story}\n\n"
                    f"Sizing de la historia {idx}:\n{story_sizing}"
                )
                qa_items.append(
                    _run_agent(
                        "Agent_Requirement_WorkFlow_06_Generator_Test_Case.md",
                        input_qa,
                    )
                )

            st.session_state.reqwf_qa_outputs = qa_items
            st.session_state.reqwf_qa_source_signature = qa_signature
            st.session_state.reqwf_qa_output = _build_qa_output(qa_items)

        if not st.session_state.reqwf_qa_outputs:
            st.warning("No se pudieron generar casos de prueba para las historias disponibles.")
        else:
            for idx, qa_text in enumerate(st.session_state.reqwf_qa_outputs, start=1):
                story_title = (
                    st.session_state.reqwf_story_titles[idx - 1]
                    if idx - 1 < len(st.session_state.reqwf_story_titles)
                    else f"Historia {idx}"
                )
                st.markdown(f"#### Casos de prueba - {story_title}")
                st.success(qa_text)

        if st.session_state.reqwf_current_step == 6 and st.button("Consolidar issue final ➔"):
            st.session_state.reqwf_current_step = 7
            st.rerun()

    if st.session_state.reqwf_current_step >= 7:
        step_header("Paso 7: Agent 07 - Issue Formatter")
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