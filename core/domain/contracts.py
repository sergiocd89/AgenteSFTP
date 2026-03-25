from typing import Any


def make_result(
    success: bool,
    message: str,
    data: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "message": message,
        "data": data,
        "error_code": error_code,
    }
