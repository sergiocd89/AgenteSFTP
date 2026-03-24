import base64
import json
import os
import urllib.error
import urllib.request


def _confluence_headers(email: str, api_token: str) -> dict[str, str]:
    auth_raw = f"{email}:{api_token}".encode("utf-8")
    b64_token = base64.b64encode(auth_raw).decode("utf-8")
    return {
        "Authorization": f"Basic {b64_token}",
        "Content-Type": "application/json",
    }


def upload_markdown_to_confluence(
    title: str,
    markdown_content: str,
    parent_id: str | None = None,
) -> tuple[bool, str]:
    """Sube contenido markdown como pagina de Confluence usando variables de entorno."""
    base_url = os.getenv("CONFLUENCE_BASE_URL", "").strip().rstrip("/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY", "").strip()
    email = os.getenv("CONFLUENCE_USER_EMAIL", "").strip()
    api_token = os.getenv("CONFLUENCE_API_TOKEN", "").strip()

    if not (base_url and space_key and email and api_token):
        return False, (
            "Faltan variables de entorno para Confluence: "
            "CONFLUENCE_BASE_URL, CONFLUENCE_SPACE_KEY, CONFLUENCE_USER_EMAIL, CONFLUENCE_API_TOKEN."
        )

    api_url = f"{base_url}/wiki/rest/api/content"
    body: dict = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
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
        headers=_confluence_headers(email, api_token),
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
