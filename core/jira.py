import base64
import json
import os
import urllib.error
import urllib.request


def _token_auth(user: str, access: str) -> str:
    """Genera token de autenticación Base64 para Jira Cloud."""
    auth_str = f"{user}:{access}"
    return base64.b64encode(auth_str.encode()).decode()


def _headers_jira() -> dict[str, str]:
    """Construye headers HTTP para Jira usando variables de entorno."""
    username = os.environ.get("JIRA_USER", "")
    password = os.environ.get("JIRA_PASSWORD", "")
    b64_auth_str = _token_auth(username, password)
    return {
        "Content-Type": "application/json",
        "Authorization": f"Basic {b64_auth_str}",
        "Accept": "application/json",
    }


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
) -> tuple[bool, str]:
    """Crea un issue en Jira Cloud usando autenticación Basic (user + token)."""
    if not base_url or not project_key:
        return False, "Debes indicar URL de Jira y Project Key."

    issue_endpoint = f"{base_url.rstrip('/')}/rest/api/3/issue"
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
        headers=_headers_jira(),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="ignore")
            parsed = json.loads(raw) if raw else {}
            issue_key = parsed.get("key", "(sin key)")
            browse_url = f"{base_url.rstrip('/')}/browse/{issue_key}" if issue_key != "(sin key)" else ""
            return True, f"Issue creado en Jira: {issue_key} {browse_url}".strip()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return False, f"Error Jira HTTP {exc.code}: {detail}"
    except Exception as exc:
        return False, f"Error al crear issue en Jira: {exc}"
