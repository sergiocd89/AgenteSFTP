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


def test_check_credentials_uses_postgres_provider(monkeypatch):
	class _FakeCursor:
		def __enter__(self):
			return self

		def __exit__(self, exc_type, exc, tb):
			return False

		def execute(self, query, params):
			self.query = query
			self.params = params

		def fetchone(self):
			return (True,)

	class _FakeConnection:
		def __enter__(self):
			return self

		def __exit__(self, exc_type, exc, tb):
			return False

		def cursor(self):
			return _FakeCursor()

	class _FakePsycopg:
		@staticmethod
		def connect(_dsn):
			return _FakeConnection()

	monkeypatch.setenv("AUTH_PROVIDER", "postgres")
	monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
	monkeypatch.setattr(utils, "psycopg", _FakePsycopg, raising=True)

	assert utils.check_credentials("tester", "secret") is True


def test_check_credentials_postgres_returns_false_on_connection_error(monkeypatch):
	class _BrokenPsycopg:
		@staticmethod
		def connect(_dsn):
			raise RuntimeError("db offline")

	monkeypatch.setenv("AUTH_PROVIDER", "postgres")
	monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
	monkeypatch.setattr(utils, "psycopg", _BrokenPsycopg, raising=True)

	assert utils.check_credentials("tester", "secret") is False


def test_check_credentials_uses_sqlserver_provider(monkeypatch):
	class _FakeCursor:
		def execute(self, *_args):
			return None

		def fetchone(self):
			return (1,)

	class _FakeConnection:
		def __enter__(self):
			return self

		def __exit__(self, exc_type, exc, tb):
			return False

		def cursor(self):
			return _FakeCursor()

	class _FakePyodbc:
		@staticmethod
		def connect(_conn_str, timeout=5):
			return _FakeConnection()

	monkeypatch.setenv("AUTH_PROVIDER", "sqlserver")
	monkeypatch.setenv("SQLSERVER_HOST", "localhost")
	monkeypatch.setenv("SQLSERVER_DATABASE", "agente_db")
	monkeypatch.setenv("SQLSERVER_USER", "sa")
	monkeypatch.setenv("SQLSERVER_PASSWORD", "secret")
	monkeypatch.setattr(utils, "pyodbc", _FakePyodbc, raising=True)

	assert utils.check_credentials("tester", "secret") is True


def test_check_credentials_sqlserver_returns_false_on_connection_error(monkeypatch):
	class _BrokenPyodbc:
		@staticmethod
		def connect(_conn_str, timeout=5):
			raise RuntimeError("sqlserver offline")

	monkeypatch.setenv("AUTH_PROVIDER", "sqlserver")
	monkeypatch.setenv("SQLSERVER_HOST", "localhost")
	monkeypatch.setenv("SQLSERVER_DATABASE", "agente_db")
	monkeypatch.setenv("SQLSERVER_USER", "sa")
	monkeypatch.setenv("SQLSERVER_PASSWORD", "secret")
	monkeypatch.setattr(utils, "pyodbc", _BrokenPyodbc, raising=True)

	assert utils.check_credentials("tester", "secret") is False


def test_change_user_password_env_success(monkeypatch):
	old_hash = hashlib.sha256("old-pass".encode()).hexdigest()
	monkeypatch.setenv("AUTH_PROVIDER", "env")
	monkeypatch.setenv("AUTH_USERS_JSON", '{"tester":"' + old_hash + '"}')

	ok, _ = utils.change_user_password("tester", "old-pass", "new-pass")
	assert ok is True
	assert utils.check_credentials("tester", "new-pass") is True
	assert utils.check_credentials("tester", "old-pass") is False


def test_change_user_password_env_rejects_invalid_current(monkeypatch):
	old_hash = hashlib.sha256("old-pass".encode()).hexdigest()
	monkeypatch.setenv("AUTH_PROVIDER", "env")
	monkeypatch.setenv("AUTH_USERS_JSON", '{"tester":"' + old_hash + '"}')

	ok, message = utils.change_user_password("tester", "wrong", "new-pass")
	assert ok is False
	assert "actual" in message.lower()
