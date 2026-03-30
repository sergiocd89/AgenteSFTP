from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_current_claims, get_current_username
from ..schemas import (
    ChangePasswordRequest,
    GenericResponse,
    LoginRequest,
    LoginResponse,
    TokenRefreshResponse,
)
from ..security import create_access_token
from ..services import authenticate_user, get_user_profile, change_user_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    username = payload.username.strip()
    if not authenticate_user(username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña inválidos.",
        )

    profile = get_user_profile(username)
    token, expires_in = create_access_token(
        subject=username,
        modules=profile["modules"],
        is_admin=profile["is_admin"],
    )
    return LoginResponse(
        success=True,
        message="Autenticación exitosa.",
        access_token=token,
        expires_in=expires_in,
        modules=profile["modules"],
        is_admin=profile["is_admin"],
    )


@router.post("/change-password", response_model=GenericResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_username: str = Depends(get_current_username),
) -> GenericResponse:
    ok, message = change_user_password(
        username=current_username,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return GenericResponse(success=True, message=message)


@router.post("/refresh", response_model=TokenRefreshResponse)
def refresh(claims: dict = Depends(get_current_claims)) -> TokenRefreshResponse:
    username = str(claims.get("sub", "")).strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sin usuario válido.")

    modules = [str(item) for item in (claims.get("modules") or [])]
    is_admin = bool(claims.get("is_admin", False))
    token, expires_in = create_access_token(subject=username, modules=modules, is_admin=is_admin)

    return TokenRefreshResponse(
        success=True,
        message="Token renovado correctamente.",
        access_token=token,
        expires_in=expires_in,
        modules=modules,
        is_admin=is_admin,
    )
