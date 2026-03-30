from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_current_claims, get_current_username
from ..schemas import (
    ProfileCreateRequest,
    ProfileOperationResponse,
    ProfileResponse,
    ProfileUpsertRequest,
)
from ..services import can_access_module, create_profile, get_user_profile, update_profile

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileResponse)
def me(current_username: str = Depends(get_current_username)) -> ProfileResponse:
    return ProfileResponse(**get_user_profile(current_username))


@router.get("/{username}", response_model=ProfileResponse)
def by_username(
    username: str,
    claims: dict = Depends(get_current_claims),
) -> ProfileResponse:
    requester = str(claims.get("sub", "")).strip()
    requester_is_admin = bool(claims.get("is_admin", False))
    if username != requester and not requester_is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden consultar perfiles de otros usuarios.",
        )
    return ProfileResponse(**get_user_profile(username))


@router.get("/me/modules/{module_key}")
def module_access(module_key: str, current_username: str = Depends(get_current_username)) -> dict:
    return {
        "success": True,
        "module_key": module_key,
        "has_access": can_access_module(current_username, module_key),
    }


@router.post("", response_model=ProfileOperationResponse)
def create(
    payload: ProfileCreateRequest,
    claims: dict = Depends(get_current_claims),
) -> ProfileOperationResponse:
    actor = str(claims.get("sub", "")).strip()
    if not bool(claims.get("is_admin", False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores pueden crear usuarios.")

    ok, message = create_profile(
        username=payload.username,
        plain_password=payload.plain_password,
        full_name=payload.full_name,
        is_admin=payload.is_admin,
        is_active=payload.is_active,
        modules=payload.modules,
        actor=actor,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return ProfileOperationResponse(success=True, message=message, username=payload.username)


@router.put("/{username}", response_model=ProfileOperationResponse)
def update(
    username: str,
    payload: ProfileUpsertRequest,
    claims: dict = Depends(get_current_claims),
) -> ProfileOperationResponse:
    actor = str(claims.get("sub", "")).strip()
    if not bool(claims.get("is_admin", False)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden actualizar perfiles de usuarios.",
        )

    ok, message = update_profile(
        username=username,
        full_name=payload.full_name,
        is_admin=payload.is_admin,
        is_active=payload.is_active,
        modules=payload.modules,
        actor=actor,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    return ProfileOperationResponse(success=True, message=message, username=username)
