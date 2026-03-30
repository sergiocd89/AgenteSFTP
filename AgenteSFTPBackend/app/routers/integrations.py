from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_current_username
from ..schemas import (
    ConfluenceMetadataRequest,
    ConfluencePublishRequest,
    IntegrationResponse,
    JiraIssueRequest,
)
from ..services import (
    can_access_module,
    create_confluence_page,
    create_jira_issue,
    get_confluence_metadata,
)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


def _raise_for_result(result: dict, default_message: str) -> None:
    if result.get("success"):
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "message": result.get("message", default_message),
            "error_code": result.get("error_code"),
        },
    )


@router.post("/jira/issue", response_model=IntegrationResponse)
def jira_issue(
    payload: JiraIssueRequest,
    current_username: str = Depends(get_current_username),
) -> IntegrationResponse:
    if not can_access_module(current_username, "RequirementWorkflow"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a integración Jira.",
        )

    result = create_jira_issue(
        base_url=payload.base_url,
        project_key=payload.project_key,
        issue_type=payload.issue_type,
        summary=payload.summary,
        description_text=payload.description_text,
        jira_user=payload.jira_user,
        jira_password=payload.jira_password,
    )
    _raise_for_result(result, "No fue posible crear issue en Jira.")

    return IntegrationResponse(
        success=True,
        message=result.get("message", "Issue creado correctamente."),
        data=result.get("data"),
        error_code=None,
    )


@router.post("/confluence/publish", response_model=IntegrationResponse)
def confluence_publish(
    payload: ConfluencePublishRequest,
    current_username: str = Depends(get_current_username),
) -> IntegrationResponse:
    if not can_access_module(current_username, "Documentation"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a integración Confluence (publish).",
        )

    result = create_confluence_page(
        title=payload.title,
        markdown_content=payload.markdown_content,
        parent_id=payload.parent_id,
        space_key=payload.space_key,
        user=payload.user,
        api_token=payload.api_token,
    )
    _raise_for_result(result, "No fue posible publicar en Confluence.")

    return IntegrationResponse(
        success=True,
        message=result.get("message", "Página publicada correctamente."),
        data=result.get("data"),
        error_code=None,
    )


@router.post("/confluence/metadata", response_model=IntegrationResponse)
def confluence_metadata(
    payload: ConfluenceMetadataRequest,
    current_username: str = Depends(get_current_username),
) -> IntegrationResponse:
    has_requirement = can_access_module(current_username, "RequirementWorkflow")
    has_documentation = can_access_module(current_username, "Documentation")
    if not (has_requirement or has_documentation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a integración Confluence (metadata).",
        )

    result = get_confluence_metadata(
        page_url=payload.page_url,
        user=payload.user,
        api_token=payload.api_token,
    )
    _raise_for_result(result, "No fue posible obtener metadata de Confluence.")

    return IntegrationResponse(
        success=True,
        message=result.get("message", "Metadata de Confluence obtenida correctamente."),
        data=result.get("data"),
        error_code=None,
    )
