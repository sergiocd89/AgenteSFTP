import io
import zipfile
from pathlib import Path

import streamlit as st

from core.domain.integration_service import publish_confluence_page
from core.ui.ai_presenter import run_llm_text
from core.utils import load_agent_prompt, step_header

_TECH_OPTIONS = [
    "AS400",
    "RPG",
    "Cobol",
    "Java",
    "ASP",
    "Visual Basic",
    "JSF",
    "React",
]

_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".rst",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".csv",
    ".ini",
    ".cfg",
    ".log",
    ".sql",
    ".py",
    ".java",
    ".cbl",
    ".cob",
    ".rpgle",
    ".cl",
    ".js",
    ".ts",
    ".tsx",
    ".jsp",
    ".vb",
    ".asp",
}


def _extract_text_from_uploaded_file(uploaded_file, max_chars: int = 18000) -> tuple[str, str]:
    """Extrae contenido util para analisis desde archivo individual o paquete .zip."""
    if uploaded_file is None:
        raise ValueError("Debe proporcionar un archivo para procesar.")
    if max_chars <= 0:
        raise ValueError("max_chars debe ser mayor a 0.")
    if not hasattr(uploaded_file, "name") or not hasattr(uploaded_file, "getvalue"):
        raise ValueError("El archivo subido no tiene el formato esperado.")

    file_name = uploaded_file.name
    suffix = Path(file_name).suffix.lower()

    if suffix == ".zip":
        zip_buffer = uploaded_file.getvalue()
        return _extract_from_zip_bytes(zip_buffer, file_name, max_chars)

    raw_bytes = uploaded_file.getvalue()
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            text = raw_bytes.decode(encoding)
            return text[:max_chars], f"Archivo leido: {file_name} ({len(text[:max_chars])} chars usados)."
        except UnicodeDecodeError:
            continue

    fallback = raw_bytes.decode("utf-8", errors="ignore")
    return fallback[:max_chars], f"Archivo leido con fallback: {file_name} ({len(fallback[:max_chars])} chars usados)."


def _extract_from_zip_bytes(zip_bytes: bytes, file_name: str, max_chars: int) -> tuple[str, str]:
    if not zip_bytes:
        raise ValueError("El contenido ZIP está vacío.")
    if max_chars <= 0:
        raise ValueError("max_chars debe ser mayor a 0.")

    snippets: list[str] = []
    inspected_files = 0
    used_chars = 0

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            for member_name in names:
                suffix = Path(member_name).suffix.lower()
                if suffix not in _TEXT_EXTENSIONS:
                    continue

                with zf.open(member_name) as member:
                    raw = member.read()

                content = ""
                for encoding in ("utf-8", "latin-1", "cp1252"):
                    try:
                        content = raw.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue

                if not content:
                    content = raw.decode("utf-8", errors="ignore")

                if not content.strip():
                    continue

                remaining = max_chars - used_chars
                if remaining <= 0:
                    break

                snippet = content[: min(2500, remaining)]
                snippets.append(f"### {member_name}\n{snippet}")
                used_chars += len(snippet)
                inspected_files += 1
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo ZIP es inválido o está corrupto.") from exc

    if not snippets:
        return "", f"Paquete {file_name} sin archivos de texto compatibles para analisis."

    summary = (
        f"Paquete leido: {file_name}. "
        f"Archivos analizados: {inspected_files}. "
        f"Caracteres usados: {used_chars}."
    )
    return "\n\n".join(snippets), summary

def show_documentation_module() -> None:
    st.title("📝 Módulo Documentación de Archivos o Paquetes")
    st.caption("Genera documentación técnica automáticamente a partir de archivos o paquetes subidos.")

    state_keys = {
        "current_step": 1,
        "technologies": [],
        "input_name": "",
        "input_content": "",
        "input_summary": "",
        "analysis_output": "",
    }

    for key, default_value in state_keys.items():
        state_key = f"doc_{key}"
        if state_key not in st.session_state:
            st.session_state[state_key] = default_value

    step_header("Paso 1: Seleccionar Tecnología")
    if st.session_state.doc_current_step == 1:
        with st.container(border=True):
            st.write("Selecciona una o más tecnologías para contextualizar la documentación:")

            selected_tech: list[str] = []
            cols = st.columns(4)
            for idx, tech in enumerate(_TECH_OPTIONS):
                with cols[idx % 4]:
                    checked = st.checkbox(tech, key=f"doc_tech_{tech}")
                    if checked:
                        selected_tech.append(tech)

            if st.button("Continuar a carga de archivo ➔", use_container_width=True, type="primary"):
                if not selected_tech:
                    st.warning("Debes seleccionar al menos una tecnología.")
                else:
                    st.session_state.doc_technologies = selected_tech
                    st.session_state.doc_current_step = 2
                    st.rerun()
    else:
        st.success("✅ Tecnologías seleccionadas: " + ", ".join(st.session_state.doc_technologies))

    if st.session_state.doc_current_step >= 2:
        step_header("Paso 2: Carga del Archivo o Paquete")
        if st.session_state.doc_current_step == 2:
            with st.container(border=True):
                uploaded = st.file_uploader(
                    "Sube un archivo de código o paquete .zip",
                    type=[
                        "txt", "md", "json", "yaml", "yml", "xml", "csv", "log", "sql",
                        "py", "java", "cbl", "cob", "rpgle", "cl", "js", "ts", "tsx", "jsp", "vb", "asp", "zip",
                    ],
                )

                if uploaded and st.button("Procesar y analizar ➔", use_container_width=True):
                    content, summary = _extract_text_from_uploaded_file(uploaded)
                    if not content.strip():
                        st.warning("No se pudo extraer contenido útil del archivo/paquete subido.")
                    else:
                        st.session_state.doc_input_name = uploaded.name
                        st.session_state.doc_input_content = content
                        st.session_state.doc_input_summary = summary
                        st.session_state.doc_current_step = 3
                        st.rerun()
        elif st.session_state.doc_input_name:
            st.success(f"✅ Entrada cargada: {st.session_state.doc_input_name}")
            st.caption(st.session_state.doc_input_summary)

    if st.session_state.doc_current_step >= 3:
        step_header("Paso 3: Respuesta del Análisis")
        if not st.session_state.doc_analysis_output:
            with st.spinner("Generando documentación técnica..."):
                sys_role = load_agent_prompt("00_documentator_readme.md")
                user_content = (
                    f"Tecnologías seleccionadas: {', '.join(st.session_state.doc_technologies)}\n"
                    f"Entrada: {st.session_state.doc_input_name}\n"
                    f"Resumen de carga: {st.session_state.doc_input_summary}\n\n"
                    "Genera documentación técnica profesional en español, enfocada en "
                    "entendimiento funcional, arquitectura, dependencias, recomendaciones "
                    "de modernización y próximos pasos.\n\n"
                    f"Contenido analizado:\n{st.session_state.doc_input_content}"
                )
                st.session_state.doc_analysis_output = run_llm_text(
                    sys_role,
                    user_content,
                    st.session_state.model_name,
                    st.session_state.temp,
                ) or "No se pudo generar la documentación para este archivo/paquete."

        st.markdown(st.session_state.doc_analysis_output)

        if st.session_state.doc_current_step == 3 and st.button("Continuar a entrega ➔"):
            st.session_state.doc_current_step = 4
            st.rerun()

    if st.session_state.doc_current_step >= 4:
        step_header("Paso 4: Descargar o Subir a Confluence")

        output_name = st.session_state.doc_input_name or "documentacion"
        safe_name = Path(output_name).stem.replace(" ", "_")

        st.download_button(
            "📥 Descargar documentación (Markdown)",
            st.session_state.doc_analysis_output,
            file_name=f"{safe_name}_documentacion.md",
            mime="text/markdown",
        )

        st.divider()
        st.markdown("#### Subir a repositorio en Confluence")

        # Fila 1: titulo completo
        confluence_title = st.text_input(
            "Título de página en Confluence",
            value=f"Documentación - {safe_name}",
            key="doc_confluence_title",
        )

        # Fila 2: space key + parent id
        col_space, col_parent = st.columns(2)
        with col_space:
            confluence_space_key = st.text_input(
                "Space Key",
                key="doc_confluence_space_key",
                placeholder="Ejemplo: CLMIGCLA",
                help=(
                    "Cómo obtenerlo desde la URL de Confluence: en rutas tipo "
                    ".../spaces/CLMIGCLA/... el Space Key es CLMIGCLA. "
                    "En algunos enlaces también aparece como parámetro spaceKey."
                ),
            )
        with col_parent:
            confluence_parent_id = st.text_input(
                "ID página padre (opcional)",
                key="doc_confluence_parent_id",
                placeholder="Ejemplo: 32165487",
                help=(
                    "Cómo obtenerlo desde la URL: abre la página padre en Confluence "
                    "y copia el valor numérico pageId del enlace, por ejemplo "
                    "...viewpage.action?pageId=32165487."
                ),
            )

        # Fila 3: usuario + password/token
        col_user, col_token = st.columns(2)
        with col_user:
            confluence_user = st.text_input(
                "Usuario",
                key="doc_confluence_user",
                placeholder="Ejemplo: SID9999999",
            )
        with col_token:
            confluence_api_token = st.text_input(
                "Password",
                key="doc_confluence_api_token",
                type="password",
                placeholder="Ejemplo: abcdef1234567890",
            )

        if st.button("⬆️ Subir a Confluence", use_container_width=True):
            result = publish_confluence_page(
                confluence_title.strip() or f"Documentación - {safe_name}",
                st.session_state.doc_analysis_output,
                confluence_parent_id.strip() or None,
                confluence_space_key.strip(),
                confluence_user.strip(),
                confluence_api_token.strip(),
            )
            if result.get("success"):
                st.success(result.get("message", "Operación completada."))
            else:
                st.error(result.get("message", "Error al subir a Confluence."))

        if st.button("🔄 Nueva documentación"):
            for key, default_value in state_keys.items():
                st.session_state[f"doc_{key}"] = default_value

            for tech in _TECH_OPTIONS:
                st.session_state[f"doc_tech_{tech}"] = False

            st.session_state.doc_confluence_title = ""
            st.session_state.doc_confluence_space_key = ""
            st.session_state.doc_confluence_user = ""
            st.session_state.doc_confluence_api_token = ""
            st.session_state.doc_confluence_parent_id = ""
            st.rerun()
