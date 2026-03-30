from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/health", tags=["health"])


@router.get("", summary="Health check")
def health() -> dict:
    return {"success": True, "status": "ok"}
