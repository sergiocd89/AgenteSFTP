from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_current_username
from ..schemas import LlmGenerateRequest, LlmGenerateResponse
from ..services import generate_llm_text

router = APIRouter(prefix="/api/v1/llm", tags=["llm"])


@router.post("/generate", response_model=LlmGenerateResponse)
def generate(
    payload: LlmGenerateRequest,
    _current_username: str = Depends(get_current_username),
) -> LlmGenerateResponse:
    result = generate_llm_text(
        system_role=payload.system_role,
        user_content=payload.user_content,
        model=payload.model,
        temp=payload.temp,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": result.get("message", "Error en llamada LLM."),
                "error_code": result.get("error_code"),
            },
        )

    data = result.get("data") or {}
    return LlmGenerateResponse(
        success=True,
        message=result.get("message", "OK"),
        content=data.get("content"),
        error_code=None,
    )
