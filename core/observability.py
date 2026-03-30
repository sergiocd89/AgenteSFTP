import uuid


def generate_request_id() -> str:
    return uuid.uuid4().hex[:12]


def format_message_with_request_id(message: str, request_id: str | None) -> str:
    text = (message or "").strip() or "Error no especificado."
    if not request_id:
        return text
    return f"{text} [request_id={request_id}]"
