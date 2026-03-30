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
- `JWT_SECRET_KEY` (recomendado, >=32 bytes)
- `JWT_ALGORITHM` (opcional, default `HS256`)
- `JWT_EXP_MINUTES` (opcional, default `60`)

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
- `POST /api/v1/profiles/{username}/reset-password` (Bearer token, solo admin)
- `POST /api/v1/llm/generate` (Bearer token)
- `POST /api/v1/workflows/{workflow}/steps/{step}` (Bearer token)
- `POST /api/v1/workflows/sftp/{step}` (Bearer token, step tipado)
- `POST /api/v1/workflows/cobol-python/{step}` (Bearer token, step tipado)
- `POST /api/v1/workflows/cobol-dtsx/{step}` (Bearer token, step tipado)
- `POST /api/v1/workflows/requirement/{step}` (Bearer token, step tipado)
- `POST /api/v1/workflows/documentation/{step}` (Bearer token, step tipado)
- `POST /api/v1/integrations/jira/issue` (Bearer token, módulo RequirementWorkflow)
- `POST /api/v1/integrations/confluence/publish` (Bearer token, módulo Documentation)
- `POST /api/v1/integrations/confluence/metadata` (Bearer token, módulo RequirementWorkflow o Documentation)

Workflows soportados en este primer corte:

- `sftp` (`analyze`, `architect`, `develop`, `audit`)
- `cobol_python` (`analyze`, `architect`, `develop`, `audit`)
- `cobol_dtsx` (`analyze`, `architect`, `develop`, `audit`)
- `requirement` (`create`, `refine`, `diagram`, `size`, `test_cases`, `format_issue`)
- `documentation` (`analyze`)

## Próximos pasos

- Endpoints dedicados para integraciones externas (`jira`, `confluence`) backend-only
- Endpoints especializados por flujo con payloads tipados por etapa
- Pruebas de contrato API por endpoint especializado
