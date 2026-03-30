from enum import Enum

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    success: bool
    message: str
    access_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    modules: list[str] = []
    is_admin: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=1)


class GenericResponse(BaseModel):
    success: bool
    message: str


class TokenRefreshResponse(BaseModel):
    success: bool
    message: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    modules: list[str] = []
    is_admin: bool = False


class ProfileResponse(BaseModel):
    username: str
    modules: list[str]
    is_admin: bool
    is_active: bool = True
    full_name: str


class ProfileUpsertRequest(BaseModel):
    full_name: str = ""
    is_admin: bool = False
    is_active: bool = True
    modules: list[str] = []


class ProfileCreateRequest(ProfileUpsertRequest):
    username: str = Field(min_length=1)
    plain_password: str = Field(min_length=1)


class ProfileOperationResponse(BaseModel):
    success: bool
    message: str
    username: str


class ProfileResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=1)


class LlmGenerateRequest(BaseModel):
    system_role: str = Field(min_length=1)
    user_content: str = Field(min_length=1)
    model: str = Field(min_length=1)
    temp: float = 0.0


class LlmGenerateResponse(BaseModel):
    success: bool
    message: str
    content: str | None = None
    error_code: str | None = None


class WorkflowStepRequest(BaseModel):
    input: str = ""
    context: str = ""
    model: str = Field(min_length=1)
    temp: float = 0.0


class WorkflowStepResponse(BaseModel):
    success: bool
    message: str
    workflow: str
    step: str
    content: str | None = None
    error_code: str | None = None


class SftpStep(str, Enum):
    analyze = "analyze"
    architect = "architect"
    develop = "develop"
    audit = "audit"


class CobolPythonStep(str, Enum):
    analyze = "analyze"
    architect = "architect"
    develop = "develop"
    audit = "audit"


class CobolDtsxStep(str, Enum):
    analyze = "analyze"
    architect = "architect"
    develop = "develop"
    audit = "audit"


class RequirementStep(str, Enum):
    create = "create"
    refine = "refine"
    diagram = "diagram"
    size = "size"
    test_cases = "test_cases"
    format_issue = "format_issue"


class DocumentationStep(str, Enum):
    analyze = "analyze"


class IntegrationResponse(BaseModel):
    success: bool
    message: str
    data: dict | None = None
    error_code: str | None = None


class JiraIssueRequest(BaseModel):
    base_url: str = Field(min_length=1)
    project_key: str = Field(min_length=1)
    issue_type: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description_text: str = ""
    jira_user: str | None = None
    jira_password: str | None = None


class ConfluencePublishRequest(BaseModel):
    title: str = Field(min_length=1)
    markdown_content: str = ""
    parent_id: str | None = None
    space_key: str | None = None
    user: str | None = None
    api_token: str | None = None


class ConfluenceMetadataRequest(BaseModel):
    page_url: str = Field(min_length=1)
    user: str = Field(min_length=1)
    api_token: str = Field(min_length=1)
