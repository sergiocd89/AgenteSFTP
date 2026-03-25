import hashlib

import pytest

from core import utils


def test_check_credentials_valid_user_with_hash(monkeypatch):
	monkeypatch.setattr(
		utils,
		"_USERS",
		{"tester": hashlib.sha256("secret".encode()).hexdigest()},
		raising=True,
	)
	assert utils.check_credentials("tester", "secret") is True


def test_check_credentials_invalid_password(monkeypatch):
	monkeypatch.setattr(
		utils,
		"_USERS",
		{"tester": hashlib.sha256("secret".encode()).hexdigest()},
		raising=True,
	)
	assert utils.check_credentials("tester", "wrong") is False


def test_step_header_requires_non_empty_text():
	with pytest.raises(ValueError):
		utils.step_header("   ")
