import importlib
import os
import sys
import types


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


def _install_streamlit_stub():
    streamlit_stub = types.ModuleType("streamlit")
    def _cache_decorator_stub(*dargs, **dkwargs):
        if dargs and callable(dargs[0]) and len(dargs) == 1 and not dkwargs:
            return dargs[0]
        return lambda fn: fn

    streamlit_stub.cache_resource = _cache_decorator_stub
    streamlit_stub.cache_data = _cache_decorator_stub
    streamlit_stub.session_state = SessionState({"model_name": "gpt-4o", "temp": 0.0})

    def _noop(*args, **kwargs):
        return None

    for name in [
        "error",
        "stop",
        "markdown",
        "divider",
        "title",
        "caption",
        "warning",
        "success",
        "info",
    ]:
        setattr(streamlit_stub, name, _noop)

    components_stub = types.ModuleType("streamlit.components")
    components_v1_stub = types.ModuleType("streamlit.components.v1")
    components_v1_stub.html = _noop

    sys.modules["streamlit"] = streamlit_stub
    sys.modules["streamlit.components"] = components_stub
    sys.modules["streamlit.components.v1"] = components_v1_stub


def _import_workflow_module():
    _install_streamlit_stub()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if root not in sys.path:
        sys.path.append(root)
    return importlib.import_module("modules.modulo_Requirement_WorkFlow")


def test_split_user_stories_by_us_markers():
    workflow = _import_workflow_module()
    text = "[US-001] A\nDetalle A\n[US-002] B\nDetalle B\n[US-003] C"

    stories = workflow._split_user_stories(text)

    assert len(stories) == 3
    assert stories[0].startswith("[US-001]")
    assert stories[1].startswith("[US-002]")
    assert stories[2].startswith("[US-003]")


def test_extract_story_title_uses_first_non_empty_line():
    workflow = _import_workflow_module()
    title = workflow._extract_story_title("\n### [US-001] Login seguro\nComo usuario...", 1)
    assert "[US-001] Login seguro" in title


def test_build_output_helpers_create_sections():
    workflow = _import_workflow_module()

    diagram_output = workflow._build_diagram_output(["D1", "D2"])
    sizer_output = workflow._build_sizer_output(["S1", "S2"])
    qa_output = workflow._build_qa_output(["Q1", "Q2"])

    assert "Diagrama Historia 1" in diagram_output
    assert "Sizing Historia 2" in sizer_output
    assert "QA Historia 2" in qa_output


def test_extract_mermaid_code_returns_first_block_only():
    workflow = _import_workflow_module()
    text = """texto\n```mermaid\nflowchart TD\nA-->B\n```\nmas texto"""
    code = workflow._extract_mermaid_code(text)
    assert "flowchart TD" in code


def test_remove_mermaid_blocks_strips_mermaid_code():
    workflow = _import_workflow_module()
    text = "inicio\n```mermaid\nflowchart TD\nA-->B\n```\nfin"
    cleaned = workflow._remove_mermaid_blocks(text)
    assert "flowchart TD" not in cleaned
    assert "inicio" in cleaned
    assert "fin" in cleaned
