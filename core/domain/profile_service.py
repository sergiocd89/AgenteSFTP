import json

from core.infrastructure import profile_db


class ProfileService:
    """Domain service for profile operations, independent of Streamlit."""

    def __init__(
        self,
        provider: str,
        database_url: str,
        sqlserver_conn_str: str,
        psycopg_module,
        pyodbc_module,
        modules: dict[str, dict],
        env_user_profiles_json: str,
        env_admins_csv: str,
    ) -> None:
        self.provider = provider
        self.database_url = database_url
        self.sqlserver_conn_str = sqlserver_conn_str
        self.psycopg_module = psycopg_module
        self.pyodbc_module = pyodbc_module
        self.modules = modules
        self.env_user_profiles_json = env_user_profiles_json
        self.env_admins_csv = env_admins_csv

    def load_profiles_and_admins(self) -> tuple[dict[str, list[str]], set[str]]:
        if self.provider in {"postgres", "postgresql", "db"}:
            loaded = self.load_profiles_and_admins_from_postgres()
            if loaded is not None:
                return loaded
        if self.provider in {"sqlserver", "mssql"}:
            loaded = self.load_profiles_and_admins_from_sqlserver()
            if loaded is not None:
                return loaded
        return self.load_profiles_and_admins_from_env()

    def load_profiles_and_admins_from_postgres(self) -> tuple[dict[str, list[str]], set[str]] | None:
        return profile_db.load_profiles_and_admins_from_postgres(
            self.database_url,
            self.psycopg_module,
        )

    def load_profiles_and_admins_from_sqlserver(self) -> tuple[dict[str, list[str]], set[str]] | None:
        return profile_db.load_profiles_and_admins_from_sqlserver(
            self.sqlserver_conn_str,
            self.pyodbc_module,
        )

    def load_user_profile_meta(self) -> dict[str, dict[str, object]] | None:
        if self.provider in {"postgres", "postgresql", "db"}:
            return self.load_user_profile_meta_from_postgres()
        if self.provider in {"sqlserver", "mssql"}:
            return self.load_user_profile_meta_from_sqlserver()
        return None

    def load_user_profile_meta_from_postgres(self) -> dict[str, dict[str, object]] | None:
        return profile_db.load_user_profile_meta_from_postgres(
            self.database_url,
            self.psycopg_module,
        )

    def load_user_profile_meta_from_sqlserver(self) -> dict[str, dict[str, object]] | None:
        return profile_db.load_user_profile_meta_from_sqlserver(
            self.sqlserver_conn_str,
            self.pyodbc_module,
        )

    def update_user_profile(
        self,
        username: str,
        full_name: str,
        is_admin_user: bool,
        is_active_user: bool,
        module_keys: list[str],
        actor: str,
    ) -> bool:
        valid_modules = set(self.modules.keys())
        if self.provider in {"postgres", "postgresql", "db"}:
            return profile_db.update_user_profile_postgres(
                self.database_url,
                self.psycopg_module,
                username,
                full_name,
                is_admin_user,
                is_active_user,
                module_keys,
                valid_modules,
                actor,
            )
        if self.provider in {"sqlserver", "mssql"}:
            return profile_db.update_user_profile_sqlserver(
                self.sqlserver_conn_str,
                self.pyodbc_module,
                username,
                full_name,
                is_admin_user,
                is_active_user,
                module_keys,
                valid_modules,
                actor,
            )
        return True

    def admin_reset_password(self, username: str, new_plain_password: str, actor: str) -> tuple[bool, str]:
        if self.provider in {"postgres", "postgresql", "db"}:
            return profile_db.admin_reset_password_postgres(
                self.database_url,
                self.psycopg_module,
                username,
                new_plain_password,
                actor,
            )
        if self.provider in {"sqlserver", "mssql"}:
            return profile_db.admin_reset_password_sqlserver(
                self.sqlserver_conn_str,
                self.pyodbc_module,
                username,
                new_plain_password,
                actor,
            )
        return False, "El reseteo de contraseña solo está disponible con AUTH_PROVIDER=postgres o AUTH_PROVIDER=sqlserver."

    def create_user_profile(
        self,
        username: str,
        plain_password: str,
        full_name: str,
        is_admin_user: bool,
        is_active_user: bool,
        module_keys: list[str],
        actor: str,
    ) -> tuple[bool, str]:
        valid_modules = set(self.modules.keys())
        if self.provider in {"postgres", "postgresql", "db"}:
            return profile_db.create_user_profile_postgres(
                self.database_url,
                self.psycopg_module,
                username,
                plain_password,
                full_name,
                is_admin_user,
                is_active_user,
                module_keys,
                valid_modules,
                actor,
            )
        if self.provider in {"sqlserver", "mssql"}:
            return profile_db.create_user_profile_sqlserver(
                self.sqlserver_conn_str,
                self.pyodbc_module,
                username,
                plain_password,
                full_name,
                is_admin_user,
                is_active_user,
                module_keys,
                valid_modules,
                actor,
            )
        return True, f"Usuario {username} creado en sesión activa (modo env)."

    def load_profiles_and_admins_from_env(self) -> tuple[dict[str, list[str]], set[str]]:
        raw_profiles = (self.env_user_profiles_json or "").strip()
        profiles: dict[str, list[str]] = {}

        if raw_profiles:
            try:
                parsed = json.loads(raw_profiles)
            except json.JSONDecodeError:
                parsed = None

            if isinstance(parsed, dict):
                valid_module_keys = set(self.modules.keys())
                for username, modules in parsed.items():
                    safe_username = str(username).strip()
                    if not safe_username or not isinstance(modules, list):
                        continue

                    filtered = [
                        str(module_key)
                        for module_key in modules
                        if str(module_key) in valid_module_keys
                    ]
                    if filtered:
                        profiles[safe_username] = filtered

        raw_admins = (self.env_admins_csv or "").strip()
        if raw_admins:
            admins = {
                admin.strip()
                for admin in raw_admins.split(",")
                if admin.strip() in profiles
            }
        else:
            admins = set()

        if not admins and profiles:
            admins = {next(iter(profiles.keys()))}

        return profiles, admins
