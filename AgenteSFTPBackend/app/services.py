import hashlib
import json
import os

from core.domain.ai_service import call_llm as domain_call_llm
from core.domain.auth_service import change_password, check_credentials
from core.domain.profile_service import ProfileService
from core.infrastructure import auth_db
from core.infrastructure.llm.factory import resolve_llm_gateway
from core.infrastructure.prompt_repository import read_agent_prompt

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

try:
    import pyodbc
except ImportError:  # pragma: no cover
    pyodbc = None


MODULES: dict[str, dict] = {
    "SFTP": {},
    "COBOL": {},
    "DTSX": {},
    "RequirementWorkflow": {},
    "Documentation": {},
}


WORKFLOW_STEP_PROMPTS: dict[str, dict[str, str]] = {
    "sftp": {
        "analyze": "01_analyst_AS400SFTP.md",
        "architect": "02_architect_AS400SFTP.md",
        "develop": "03_developer_AS400SFTP.md",
        "audit": "04_auditor_AS400SFTP.md",
    },
    "cobol_python": {
        "analyze": "01_analyst_CobolToPython.md",
        "architect": "02_architect_CobolToPython.md",
        "develop": "03_developer_CobolToPython.md",
        "audit": "04_auditor_CobolToPython.md",
    },
    "cobol_dtsx": {
        "analyze": "01_analyst_CobolToDtsx.md",
        "architect": "02_architect_CobolToDtsx.md",
        "develop": "03_developer_CobolToDtsx.md",
        "audit": "04_auditor_CobolToDtsx.md",
    },
    "requirement": {
        "create": "Agent_Requirement_WorkFlow_01_Creator_Use_Case.md",
        "refine": "Agent_Requirement_WorkFlow_02_Refiner_Use_Case.md",
        "diagram": "Agent_Requirement_WorkFlow_04_Diagram_Use_Case.md",
        "size": "Agent_Requirement_WorkFlow_05_Sizer.md",
        "test_cases": "Agent_Requirement_WorkFlow_06_Generator_Test_Case.md",
        "format_issue": "Agent_Requirement_WorkFlow_07_issue_formatter.md",
    },
    "documentation": {
        "analyze": "00_documentator.md",
    },
}


WORKFLOW_MODULE_MAP: dict[str, str] = {
    "sftp": "SFTP",
    "cobol_python": "COBOL",
    "cobol_dtsx": "DTSX",
    "requirement": "RequirementWorkflow",
    "documentation": "Documentation",
}


def load_users_from_env() -> dict[str, str]:
    raw_json = os.getenv("AUTH_USERS_JSON", "").strip()
    if raw_json:
        try:
            loaded = json.loads(raw_json)
            if isinstance(loaded, dict):
                return {
                    str(user).strip(): str(password_hash).strip()
                    for user, password_hash in loaded.items()
                    if str(user).strip() and str(password_hash).strip()
                }
        except json.JSONDecodeError:
            return {}

    single_user = os.getenv("AUTH_USER", "").strip()
    single_password = os.getenv("AUTH_PASSWORD", "").strip()
    if single_user and single_password:
        return {single_user: hashlib.sha256(single_password.encode()).hexdigest()}

    return {}


def authenticate_user(username: str, password: str) -> bool:
    return check_credentials(
        username=username,
        password=password,
        users=load_users_from_env(),
        psycopg_module=psycopg,
        pyodbc_module=pyodbc,
    )


def change_user_password(username: str, current_password: str, new_password: str) -> tuple[bool, str]:
    users = load_users_from_env()
    ok, message = change_password(
        username=username,
        current_password=current_password,
        new_password=new_password,
        users=users,
        psycopg_module=psycopg,
        pyodbc_module=pyodbc,
    )

    if ok and auth_db.get_auth_provider() in {"env", ""}:
        os.environ["AUTH_USERS_JSON"] = json.dumps(users)

    return ok, message


def build_profile_service() -> ProfileService:
    return ProfileService(
        provider=auth_db.get_auth_provider(),
        database_url=auth_db.get_database_url(),
        sqlserver_conn_str=auth_db.build_sqlserver_conn_str(),
        psycopg_module=psycopg,
        pyodbc_module=pyodbc,
        modules=MODULES,
        env_user_profiles_json=os.getenv("USER_PROFILES_JSON", ""),
        env_admins_csv=os.getenv("ADMINS_CSV", ""),
    )


def get_user_profile(username: str) -> dict:
    service = build_profile_service()
    profiles, admins = service.load_profiles_and_admins()
    meta = service.load_user_profile_meta() or {}

    safe_username = (username or "").strip()
    modules = list(profiles.get(safe_username, []))
    user_meta = meta.get(safe_username, {})

    return {
        "username": safe_username,
        "modules": modules,
        "is_admin": safe_username in admins,
        "is_active": bool(user_meta.get("is_active", True)),
        "full_name": str(user_meta.get("full_name", safe_username)),
    }


def can_access_module(username: str, module_key: str) -> bool:
    profile = get_user_profile(username)
    return module_key in profile["modules"]


def update_profile(
    username: str,
    full_name: str,
    is_admin: bool,
    is_active: bool,
    modules: list[str],
    actor: str,
) -> tuple[bool, str]:
    service = build_profile_service()
    ok = service.update_user_profile(
        username=(username or "").strip(),
        full_name=(full_name or "").strip(),
        is_admin_user=bool(is_admin),
        is_active_user=bool(is_active),
        module_keys=[str(item).strip() for item in (modules or []) if str(item).strip()],
        actor=(actor or "system").strip() or "system",
    )
    if not ok:
        return False, "No fue posible actualizar perfil en el proveedor activo."
    return True, "Perfil actualizado correctamente."


def create_profile(
    username: str,
    plain_password: str,
    full_name: str,
    is_admin: bool,
    is_active: bool,
    modules: list[str],
    actor: str,
) -> tuple[bool, str]:
    service = build_profile_service()
    return service.create_user_profile(
        username=(username or "").strip(),
        plain_password=plain_password,
        full_name=(full_name or "").strip(),
        is_admin_user=bool(is_admin),
        is_active_user=bool(is_active),
        module_keys=[str(item).strip() for item in (modules or []) if str(item).strip()],
        actor=(actor or "system").strip() or "system",
    )


def reset_profile_password(username: str, new_password: str, actor: str) -> tuple[bool, str]:
    service = build_profile_service()
    return service.admin_reset_password(
        username=(username or "").strip(),
        new_plain_password=new_password,
        actor=(actor or "system").strip() or "system",
    )


def generate_llm_text(system_role: str, user_content: str, model: str, temp: float) -> dict:
    gateway, provider = resolve_llm_gateway()
    if gateway is None:
        return {
            "success": False,
            "message": f"Proveedor LLM no soportado: {provider}",
            "data": None,
            "error_code": "missing_gateway",
        }

    return domain_call_llm(
        system_role=system_role,
        user_content=user_content,
        model=model,
        temp=temp,
        llm_gateway=gateway,
    )


def get_workflow_module_key(workflow: str) -> str | None:
    return WORKFLOW_MODULE_MAP.get((workflow or "").strip().lower())


def execute_workflow_step(
    workflow: str,
    step: str,
    source_input: str,
    context: str,
    model: str,
    temp: float,
) -> dict:
    workflow_key = (workflow or "").strip().lower()
    step_key = (step or "").strip().lower()

    prompts = WORKFLOW_STEP_PROMPTS.get(workflow_key)
    if not prompts:
        return {
            "success": False,
            "message": f"Workflow no soportado: {workflow}",
            "data": None,
            "error_code": "unsupported_workflow",
        }

    prompt_file = prompts.get(step_key)
    if not prompt_file:
        return {
            "success": False,
            "message": f"Step no soportado para workflow {workflow}: {step}",
            "data": None,
            "error_code": "unsupported_step",
        }

    system_role = read_agent_prompt(prompt_file)

    source = (source_input or "").strip()
    ctx = (context or "").strip()
    if source and ctx:
        user_content = f"Entrada principal:\n{source}\n\nContexto adicional:\n{ctx}"
    else:
        user_content = source or ctx

    if not user_content:
        return {
            "success": False,
            "message": "Debes enviar input o contexto para ejecutar el workflow.",
            "data": None,
            "error_code": "missing_input",
        }

    return generate_llm_text(system_role=system_role, user_content=user_content, model=model, temp=temp)
