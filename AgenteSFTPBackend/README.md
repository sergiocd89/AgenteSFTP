# AgenteSFTPBackend

Backend inicial para la separación de componentes del proyecto AgenteSFTP.

## Alcance inicial

- API FastAPI con versionado base en `/api/v1`
- Autenticación por proveedor existente (`AUTH_PROVIDER=env|postgres|sqlserver`)
- Emisión/validación de JWT
- Endpoints de perfiles básicos

## Estructura

- `app/main.py`: inicialización FastAPI y middlewares
- `app/routers/auth.py`: login y cambio de contraseña autenticado
- `app/routers/profiles.py`: perfil propio y validación de acceso a módulo
- `app/routers/health.py`: health check
- `app/security.py`: JWT
- `app/services.py`: adaptadores hacia dominio/infra actual

## Variables requeridas

Reutiliza el `.env` raíz del proyecto actual para:

- `AUTH_PROVIDER`
- `DATABASE_URL` (si aplica)
- `SQLSERVER_*` (si aplica)
- `AUTH_USERS_JSON` o `AUTH_USER`/`AUTH_PASSWORD` (modo env)
- `USER_PROFILES_JSON`, `ADMINS_CSV`
- `JWT_SECRET_KEY` (recomendado)

## Ejecutar local

Desde la raíz del repo:

```powershell
pip install -r AgenteSFTPBackend/requirements.txt
python -m uvicorn AgenteSFTPBackend.app.main:app --reload --port 8000
```

## Endpoints iniciales

- `GET /api/v1/health`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/change-password` (Bearer token)
- `POST /api/v1/auth/refresh` (Bearer token)
- `GET /api/v1/profiles/me` (Bearer token)
- `GET /api/v1/profiles/{username}` (Bearer token, admin para terceros)
- `GET /api/v1/profiles/me/modules/{module_key}` (Bearer token)
- `POST /api/v1/profiles` (Bearer token, solo admin)
- `PUT /api/v1/profiles/{username}` (Bearer token, solo admin)
- `POST /api/v1/llm/generate` (Bearer token)

## Próximos pasos

- Endpoint de LLM (`/api/v1/llm/generate`)
- Endpoints de workflows (`sftp`, `cobol`, `dtsx`, `requirement`, `documentation`)
- Pruebas de contrato API
