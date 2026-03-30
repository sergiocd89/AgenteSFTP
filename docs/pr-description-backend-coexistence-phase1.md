# PR: Backend Coexistence Phase 1 (Streamlit + FastAPI)

## Resumen

Este PR implementa la fase inicial de separación de componentes manteniendo coexistencia controlada entre la UI Streamlit actual y un backend FastAPI nuevo.

Incluye:

- Backend FastAPI en `AgenteSFTPBackend` con autenticación JWT.
- Endpoints de auth, perfiles y LLM con pruebas de contrato.
- Integración progresiva de Streamlit hacia backend con fallback local.
- Manejo de expiración/refresh de token, reintento tras 401 y auto-logout opcional.
- Documentación operativa para despliegue y revisión.

## Alcance funcional

### Backend (`AgenteSFTPBackend`)

- Auth:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/change-password`
  - `POST /api/v1/auth/refresh`
- Profiles:
  - `GET /api/v1/profiles/me`
  - `GET /api/v1/profiles/{username}`
  - `GET /api/v1/profiles/me/modules/{module_key}`
  - `POST /api/v1/profiles` (admin)
  - `PUT /api/v1/profiles/{username}` (admin)
  - `POST /api/v1/profiles/{username}/reset-password` (admin)
- LLM:
  - `POST /api/v1/llm/generate`

### Front coexistente (Streamlit)

- Login y cambio de contraseña consumen backend cuando `BACKEND_API_ENABLED=true`.
- Perfiles y control de acceso por módulo consumen backend con fallback local.
- LLM consume backend con fallback local.
- Refresh de token preventivo y forzado cuando aplica.
- Reintento de operación tras error de autenticación.
- Banner de sesión backend inválida.
- Auto-logout opcional al fallar refresh forzado:
  - `BACKEND_AUTO_LOGOUT_ON_AUTH_FAILURE=true|false`

## Variables nuevas/relevantes

- `BACKEND_API_ENABLED`
- `BACKEND_API_BASE_URL`
- `BACKEND_AUTO_LOGOUT_ON_AUTH_FAILURE`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `JWT_EXP_MINUTES`

## Evidencia de pruebas

Ejecutado durante la implementación:

- `python -m pytest tests/test_login.py tests/test_perfil.py tests/test_utils.py -q`
  - Resultado: `38 passed`
- `python -m pytest AgenteSFTPBackend/tests -q`
  - Resultado: `17 passed`

## Riesgos y mitigación

- Riesgo: backend no disponible con coexistencia activada.
  - Mitigación: fallback local y aviso de sesión backend inválida.
- Riesgo: token expirado durante operación.
  - Mitigación: refresh preventivo/forzado + reintento único.
- Riesgo: sesión inconsistente tras falla de refresh forzado.
  - Mitigación: auto-logout configurable (`BACKEND_AUTO_LOGOUT_ON_AUTH_FAILURE`).

## Plan de rollback

- Desactivar coexistencia:
  - `BACKEND_API_ENABLED=false`
- Mantener operación Streamlit local sin backend.
- Revertir rama de feature si se requiere.

## Checklist de revisión

- [ ] Validar endpoints backend en ambiente de prueba.
- [ ] Validar login, perfiles y LLM desde Streamlit con `BACKEND_API_ENABLED=true`.
- [ ] Validar fallback con `BACKEND_API_ENABLED=false`.
- [ ] Validar comportamiento con `BACKEND_AUTO_LOGOUT_ON_AUTH_FAILURE=true` y `false`.
- [ ] Confirmar secreto JWT fuerte en ambiente (`JWT_SECRET_KEY` >= 32 bytes).

## Referencias

- Checklist operativo: `docs/pr-checklist-backend-coexistence.md`
- Rama: `feature/backend-coexistence-phase1`
