import os


def as_bool(raw: str, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


class Settings:
    api_title = os.getenv("BACKEND_API_TITLE", "AgenteSFTP Backend API")
    api_version = os.getenv("BACKEND_API_VERSION", "0.1.0")
    jwt_secret_key = os.getenv(
        "JWT_SECRET_KEY",
        os.getenv("SECRET_KEY", "change-me-in-env-with-at-least-32-bytes"),
    )
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_exp_minutes = int(os.getenv("JWT_EXP_MINUTES", "60"))
    cors_origins = [
        origin.strip()
        for origin in os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000,http://localhost:8501").split(",")
        if origin.strip()
    ]
    docs_enabled = as_bool(os.getenv("BACKEND_DOCS_ENABLED", "true"), default=True)


settings = Settings()
