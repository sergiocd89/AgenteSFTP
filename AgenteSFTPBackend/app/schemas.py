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
