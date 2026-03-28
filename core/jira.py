import base64
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from core.logger import get_logger, log_operation


def _result(success: bool, message: str, data: dict | None = None, error_code: str | None = None) -> dict:
    return {
        "success": success,
        "message": message,
        "data": data,
        "error_code": error_code,
    }


logger = get_logger(__name__)


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
        if parsed < 0:
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def _compute_retry_delay(attempt: int, backoff: float, retry_after: str | None = None) -> float:
    retry_after_seconds = _safe_float(retry_after)
    if retry_after_seconds is not None:
        # Jira puede responder 429 con Retry-After; se prioriza ese valor.
        return min(retry_after_seconds, 60.0)

    # Exponential backoff con jitter suave para evitar thundering herd.
    base_delay = backoff * (2 ** attempt)
    jitter = random.uniform(0.0, backoff)
    return min(base_delay + jitter, 60.0)


def _token_auth(user: str, access: str) -> str:
    """Genera token de autenticación Base64 para Jira Cloud."""
    auth_str = f"{user}:{access}"
    return base64.b64encode(auth_str.encode()).decode()


def _headers_jira(user: str | None = None, password: str | None = None) -> dict[str, str]:
    """Construye headers HTTP para Jira usando credenciales UI o variables de entorno."""
    username = (user or os.environ.get("JIRA_USER", "")).strip()
    password = (password or os.environ.get("JIRA_PASSWORD", "")).strip()
    b64_auth_str = _token_auth(username, password)
    return {
        "Content-Type": "application/json",
        "Authorization": f"Basic {b64_auth_str}",
        "Accept": "application/json",
    }


def _request_with_retries(req: urllib.request.Request, timeout: int) -> bytes:
    retries = int(os.getenv("HTTP_MAX_RETRIES", "4"))
    backoff = float(os.getenv("HTTP_BACKOFF_SECONDS", "0.5"))

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            should_retry = exc.code in {429, 500, 502, 503, 504}
            if should_retry and attempt < retries:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                wait_seconds = _compute_retry_delay(attempt, backoff, retry_after)
                logger.warning(
                    "operation=jira_http_retry | status=retrying | details=status=%s attempt=%s wait=%.2fs",
                    exc.code,
                    attempt + 1,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue
            raise
        except urllib.error.URLError:
            if attempt < retries:
                wait_seconds = _compute_retry_delay(attempt, backoff)
                logger.warning(
                    "operation=jira_http_retry | status=retrying | details=status=url_error attempt=%s wait=%.2fs",
                    attempt + 1,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue
            raise

    return b""


def jira_wiki_to_adf(text: str) -> dict:
    """Convierte texto plano a una estructura ADF básica para Jira Cloud."""
    lines = [line for line in (text or "").splitlines() if line.strip()]
    content = []
    for line in lines:
        content.append(
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": line[:3000]}],
            }
        )

    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": "Sin contenido."}]}]

    return {"type": "doc", "version": 1, "content": content}


def create_jira_issue(
    base_url: str,
    project_key: str,
    issue_type: str,
    summary: str,
    description_text: str,
    jira_user: str | None = None,
    jira_password: str | None = None,
) -> dict:
    """Crea un issue en Jira Cloud usando autenticación Basic (user + token)."""
    if not base_url or not project_key:
        result = _result(False, "Debes indicar URL de Jira y Project Key.", error_code="validation_error")
        log_operation(logger, "jira_create_issue", False, result["error_code"], result["message"])
        return result

    parsed_url = urllib.parse.urlparse(base_url.strip())
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        result = _result(False, "La URL de Jira no es válida (http/https).", error_code="validation_error")
        log_operation(logger, "jira_create_issue", False, result["error_code"], result["message"])
        return result

    if not issue_type.strip() or not summary.strip():
        result = _result(False, "Debes indicar Issue Type y Summary para crear el issue.", error_code="validation_error")
        log_operation(logger, "jira_create_issue", False, result["error_code"], result["message"])
        return result

    effective_user = (jira_user or os.environ.get("JIRA_USER", "")).strip()
    effective_password = (jira_password or os.environ.get("JIRA_PASSWORD", "")).strip()
    if not effective_user or not effective_password:
        result = _result(False, "Debes ingresar JIRA_USER y JIRA_PASSWORD para publicar en Jira.", error_code="validation_error")
        log_operation(logger, "jira_create_issue", False, result["error_code"], result["message"])
        return result

    normalized_base_url = base_url.strip().rstrip("/")
    issue_endpoint = f"{normalized_base_url}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary[:255],
            "issuetype": {"name": issue_type},
            "description": jira_wiki_to_adf(description_text),
        }
    }

    req = urllib.request.Request(
        issue_endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers_jira(effective_user, effective_password),
        method="POST",
    )

    timeout = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))

    try:
        raw_bytes = _request_with_retries(req, timeout=timeout)
        raw = raw_bytes.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            result = _result(False, "Jira respondió un JSON inválido.", error_code="invalid_json")
            log_operation(logger, "jira_create_issue", False, result["error_code"], result["message"])
            return result

        issue_key = parsed.get("key", "(sin key)")
        browse_url = f"{normalized_base_url}/browse/{issue_key}" if issue_key != "(sin key)" else ""
        data = {
            "issue_key": issue_key if issue_key != "(sin key)" else "",
            "browse_url": browse_url,
        }
        result = _result(True, f"Issue creado en Jira: {issue_key} {browse_url}".strip(), data=data)
        log_operation(logger, "jira_create_issue", True)
        return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        result = _result(False, f"Error Jira HTTP {exc.code}: {detail}", error_code="http_error")
        log_operation(logger, "jira_create_issue", False, result["error_code"], f"status={exc.code}")
        return result
    except Exception as exc:
        result = _result(False, f"Error al crear issue en Jira: {exc}", error_code="unexpected_error")
        log_operation(logger, "jira_create_issue", False, result["error_code"], str(exc))
        return result
