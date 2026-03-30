from core.observability import format_message_with_request_id, generate_request_id


def test_generate_request_id_has_expected_length():
    value = generate_request_id()

    assert isinstance(value, str)
    assert len(value) == 12


def test_format_message_with_request_id_handles_empty_message():
    message = format_message_with_request_id("", "abc123")

    assert "Error no especificado." in message
    assert "request_id=abc123" in message


def test_format_message_with_request_id_without_request_id():
    message = format_message_with_request_id("Error de backend", None)

    assert message == "Error de backend"
