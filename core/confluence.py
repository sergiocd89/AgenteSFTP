import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from core.logger import get_logger, log_operation


class ConfluenceResult(dict):
    """Backward-compatible result for legacy tuple unpacking and dict access."""

    def __iter__(self):
        return iter((self.get("success"), self.get("message")))


def _result(success: bool, message: str, data: dict | None = None, error_code: str | None = None) -> ConfluenceResult:
    return ConfluenceResult({
        "success": success,
        "message": message,
        "data": data,
        "error_code": error_code,
    })


logger = get_logger(__name__)


def _is_valid_http_url(url: str) -> bool:
    parsed = urllib.parse.urlparse((url or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _confluence_headers(user: str, api_token: str) -> dict[str, str]:
    auth_raw = f"{user}:{api_token}".encode("utf-8")
    b64_token = base64.b64encode(auth_raw).decode("utf-8")
    return {
        "Authorization": f"Basic {b64_token}",
        "Content-Type": "application/json",
    }


def _request_with_retries(req: urllib.request.Request, timeout: int) -> bytes:
    retries = int(os.getenv("HTTP_MAX_RETRIES", "2"))
    backoff = float(os.getenv("HTTP_BACKOFF_SECONDS", "0.5"))

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            should_retry = exc.code in {429, 500, 502, 503, 504}
            if should_retry and attempt < retries:
                time.sleep(backoff * (2 ** attempt))
                continue
            raise
        except urllib.error.URLError:
            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
                continue
            raise

    return b""


def upload_markdown_to_confluence(
    title: str,
    markdown_content: str,
    parent_id: str | None = None,
    space_key: str | None = None,
    user: str | None = None,
    api_token: str | None = None,
) -> dict:
    """Sube contenido markdown como pagina de Confluence.

    Prioriza credenciales recibidas por parametro y usa variables de entorno como fallback.
    """
    base_url = os.getenv("CONFLUENCE_BASE_URL", "").strip().rstrip("/")
    final_space_key = (space_key or os.getenv("CONFLUENCE_SPACE_KEY", "")).strip()
    final_user = (user or os.getenv("CONFLUENCE_USER", "")).strip()
    final_api_token = (api_token or os.getenv("CONFLUENCE_API_TOKEN", "")).strip()

    if not (base_url and final_space_key and final_user and final_api_token):
        result = _result(False, (
            "Faltan datos para Confluence. Revisa CONFLUENCE_BASE_URL y completa en pantalla "
            "(o por variables de entorno) CONFLUENCE_SPACE_KEY, CONFLUENCE_USER/CONFLUENCE_USER y CONFLUENCE_API_TOKEN."
        ), error_code="validation_error")
        log_operation(logger, "confluence_upload", False, result["error_code"], result["message"])
        return result

    if not _is_valid_http_url(base_url):
        result = _result(False, "CONFLUENCE_BASE_URL no es una URL válida (http/https).", error_code="validation_error")
        log_operation(logger, "confluence_upload", False, result["error_code"], result["message"])
        return result

    api_url = f"{base_url}/rest/api/content"
    body: dict = {
        "type": "page",
        "title": title,
        "space": {"key": final_space_key},
        "body": {
            "storage": {
                "value": f"<pre>{markdown_content}</pre>",
                "representation": "storage",
            }
        },
    }

    if parent_id:
        body["ancestors"] = [{"id": parent_id}]

    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode("utf-8"),
        headers=_confluence_headers(final_user, final_api_token),
        method="POST",
    )

    timeout = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))

    try:
        raw_bytes = _request_with_retries(req, timeout=timeout)
        raw = raw_bytes.decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            result = _result(False, "Confluence respondió un JSON inválido.", error_code="invalid_json")
            log_operation(logger, "confluence_upload", False, result["error_code"], result["message"])
            return result

        link = payload.get("_links", {}).get("webui", "")
        data = {
            "base_url": base_url,
            "webui": link,
            "page_url": f"{base_url}{link}" if link else "",
        }
        if link:
            result = _result(True, f"Documento subido exitosamente: {base_url}{link}", data=data)
            log_operation(logger, "confluence_upload", True)
            return result
        result = _result(True, "Documento subido exitosamente a Confluence.", data=data)
        log_operation(logger, "confluence_upload", True)
        return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        result = _result(False, f"Error Confluence HTTP {exc.code}: {detail}", error_code="http_error")
        log_operation(logger, "confluence_upload", False, result["error_code"], f"status={exc.code}")
        return result
    except Exception as exc:
        result = _result(False, f"Error al subir a Confluence: {exc}", error_code="unexpected_error")
        log_operation(logger, "confluence_upload", False, result["error_code"], str(exc))
        return result


def _extract_page_id_from_link(page_url: str) -> str | None:
    """Extrae pageId desde links de Confluence Cloud/Data Center."""
    if not page_url:
        return None

    parsed = urllib.parse.urlparse(page_url)
    query = urllib.parse.parse_qs(parsed.query)
    page_id = (query.get("pageId") or [None])[0]
    if page_id:
        return str(page_id).strip()

    match = re.search(r"/pages/(\d+)", parsed.path)
    if match:
        return match.group(1)

    return None


def get_confluence_page_metadata_from_link(
    page_url: str,
    user: str,
    api_token: str,
) -> dict:
    """Obtiene metadata de una página de Confluence a partir de su link.

    Retorna base_url, page_id, title, space_key y parent_id.
    """
    safe_url = (page_url or "").strip()
    safe_user = (user or "").strip()
    safe_token = (api_token or "").strip()

    if not (safe_url and safe_user and safe_token):
        result = _result(False, "Debe completar link de Confluence, usuario y contraseña/token.", error_code="validation_error")
        log_operation(logger, "confluence_metadata", False, result["error_code"], result["message"])
        return result

    parsed = urllib.parse.urlparse(safe_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        result = _result(False, "El link de Confluence no es valido.", error_code="validation_error")
        log_operation(logger, "confluence_metadata", False, result["error_code"], result["message"])
        return result

    page_id = _extract_page_id_from_link(safe_url)
    if not page_id:
        result = _result(False, "No se pudo extraer el pageId desde el link de Confluence.", error_code="validation_error")
        log_operation(logger, "confluence_metadata", False, result["error_code"], result["message"])
        return result

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    api_url = (
        f"{base_url}/wiki/rest/api/content/{page_id}"
        "?expand=space,ancestors"
    )

    req = urllib.request.Request(
        api_url,
        headers=_confluence_headers(safe_user, safe_token),
        method="GET",
    )

    timeout = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))

    try:
        raw_bytes = _request_with_retries(req, timeout=timeout)
        raw = raw_bytes.decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            result = _result(False, "Confluence respondió metadata con JSON inválido.", error_code="invalid_json")
            log_operation(logger, "confluence_metadata", False, result["error_code"], result["message"])
            return result

        ancestors = payload.get("ancestors") or []
        parent_id = str(ancestors[-1].get("id")) if ancestors else ""

        metadata = {
            "base_url": base_url,
            "page_id": str(payload.get("id") or page_id),
            "title": payload.get("title") or "",
            "space_key": (payload.get("space") or {}).get("key") or "",
            "parent_id": parent_id,
        }
        result = _result(True, "Metadata de Confluence obtenida correctamente.", data=metadata)
        log_operation(logger, "confluence_metadata", True)
        return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        result = _result(False, f"Error Confluence HTTP {exc.code}: {detail}", error_code="http_error")
        log_operation(logger, "confluence_metadata", False, result["error_code"], f"status={exc.code}")
        return result
    except Exception as exc:
        result = _result(False, f"Error al consultar Confluence: {exc}", error_code="unexpected_error")
        log_operation(logger, "confluence_metadata", False, result["error_code"], str(exc))
        return result
