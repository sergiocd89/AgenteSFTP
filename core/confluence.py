import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


def _confluence_headers(user: str, api_token: str) -> dict[str, str]:
    auth_raw = f"{user}:{api_token}".encode("utf-8")
    b64_token = base64.b64encode(auth_raw).decode("utf-8")
    return {
        "Authorization": f"Basic {b64_token}",
        "Content-Type": "application/json",
    }


def upload_markdown_to_confluence(
    title: str,
    markdown_content: str,
    parent_id: str | None = None,
    space_key: str | None = None,
    user: str | None = None,
    api_token: str | None = None,
) -> tuple[bool, str]:
    """Sube contenido markdown como pagina de Confluence.

    Prioriza credenciales recibidas por parametro y usa variables de entorno como fallback.
    """
    base_url = os.getenv("CONFLUENCE_BASE_URL", "").strip().rstrip("/")
    final_space_key = (space_key or os.getenv("CONFLUENCE_SPACE_KEY", "")).strip()
    final_user = (user or os.getenv("CONFLUENCE_USER", "")).strip()
    final_api_token = (api_token or os.getenv("CONFLUENCE_API_TOKEN", "")).strip()

    if not (base_url and final_space_key and final_user and final_api_token):
        return False, (
            "Faltan datos para Confluence. Revisa CONFLUENCE_BASE_URL y completa en pantalla "
            "(o por variables de entorno) CONFLUENCE_SPACE_KEY, CONFLUENCE_USER/CONFLUENCE_USER y CONFLUENCE_API_TOKEN."
        )

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

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            payload = json.loads(raw) if raw else {}
            link = payload.get("_links", {}).get("webui", "")
            if link:
                return True, f"Documento subido exitosamente: {base_url}{link}"
            return True, "Documento subido exitosamente a Confluence."
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return False, f"Error Confluence HTTP {exc.code}: {detail}"
    except Exception as exc:
        return False, f"Error al subir a Confluence: {exc}"


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
) -> tuple[bool, dict | str]:
    """Obtiene metadata de una página de Confluence a partir de su link.

    Retorna base_url, page_id, title, space_key y parent_id.
    """
    safe_url = (page_url or "").strip()
    safe_user = (user or "").strip()
    safe_token = (api_token or "").strip()

    if not (safe_url and safe_user and safe_token):
        return False, "Debe completar link de Confluence, usuario y contraseña/token."

    parsed = urllib.parse.urlparse(safe_url)
    if not (parsed.scheme and parsed.netloc):
        return False, "El link de Confluence no es valido."

    page_id = _extract_page_id_from_link(safe_url)
    if not page_id:
        return False, "No se pudo extraer el pageId desde el link de Confluence."

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

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            payload = json.loads(raw) if raw else {}

            ancestors = payload.get("ancestors") or []
            parent_id = str(ancestors[-1].get("id")) if ancestors else ""

            metadata = {
                "base_url": base_url,
                "page_id": str(payload.get("id") or page_id),
                "title": payload.get("title") or "",
                "space_key": (payload.get("space") or {}).get("key") or "",
                "parent_id": parent_id,
            }
            return True, metadata
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return False, f"Error Confluence HTTP {exc.code}: {detail}"
    except Exception as exc:
        return False, f"Error al consultar Confluence: {exc}"
