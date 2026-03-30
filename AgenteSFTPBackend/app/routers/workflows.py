from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_current_username
from ..schemas import (
    CobolDtsxStep,
    CobolPythonStep,
    DocumentationStep,
    RequirementStep,
    SftpStep,
    WorkflowStepRequest,
    WorkflowStepResponse,
)
from ..services import can_access_module, execute_workflow_step, get_workflow_module_key

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


def _run_step_with_acl(
    workflow: str,
    step: str,
    payload: WorkflowStepRequest,
    current_username: str,
) -> WorkflowStepResponse:
    module_key = get_workflow_module_key(workflow)
    if not module_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow no soportado: {workflow}")

    if not can_access_module(current_username, module_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No tienes acceso al workflow {workflow}.",
        )

    result = execute_workflow_step(
        workflow=workflow,
        step=step,
        source_input=payload.input,
        context=payload.context,
        model=payload.model,
        temp=payload.temp,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": result.get("message", "Error en ejecución de workflow."),
                "error_code": result.get("error_code"),
            },
        )

    data = result.get("data") or {}
    return WorkflowStepResponse(
        success=True,
        message=result.get("message", "OK"),
        workflow=workflow,
        step=step,
        content=data.get("content"),
        error_code=None,
    )


@router.post("/{workflow}/steps/{step}", response_model=WorkflowStepResponse)
def run_step(
    workflow: str,
    step: str,
    payload: WorkflowStepRequest,
    current_username: str = Depends(get_current_username),
) -> WorkflowStepResponse:
    return _run_step_with_acl(
        workflow=workflow,
        step=step,
        payload=payload,
        current_username=current_username,
    )


@router.post("/sftp/{step}", response_model=WorkflowStepResponse)
def run_sftp_step(
    step: SftpStep,
    payload: WorkflowStepRequest,
    current_username: str = Depends(get_current_username),
) -> WorkflowStepResponse:
    return _run_step_with_acl("sftp", step.value, payload, current_username)


@router.post("/cobol-python/{step}", response_model=WorkflowStepResponse)
def run_cobol_python_step(
    step: CobolPythonStep,
    payload: WorkflowStepRequest,
    current_username: str = Depends(get_current_username),
) -> WorkflowStepResponse:
    return _run_step_with_acl("cobol_python", step.value, payload, current_username)


@router.post("/cobol-dtsx/{step}", response_model=WorkflowStepResponse)
def run_cobol_dtsx_step(
    step: CobolDtsxStep,
    payload: WorkflowStepRequest,
    current_username: str = Depends(get_current_username),
) -> WorkflowStepResponse:
    return _run_step_with_acl("cobol_dtsx", step.value, payload, current_username)


@router.post("/requirement/{step}", response_model=WorkflowStepResponse)
def run_requirement_step(
    step: RequirementStep,
    payload: WorkflowStepRequest,
    current_username: str = Depends(get_current_username),
) -> WorkflowStepResponse:
    return _run_step_with_acl("requirement", step.value, payload, current_username)


@router.post("/documentation/{step}", response_model=WorkflowStepResponse)
def run_documentation_step(
    step: DocumentationStep,
    payload: WorkflowStepRequest,
    current_username: str = Depends(get_current_username),
) -> WorkflowStepResponse:
    return _run_step_with_acl("documentation", step.value, payload, current_username)
