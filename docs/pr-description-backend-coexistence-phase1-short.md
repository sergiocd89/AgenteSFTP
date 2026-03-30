# PR Summary (Corto)

Este PR implementa la fase 1 de coexistencia entre Streamlit y un nuevo backend FastAPI.

Incluye backend con JWT y endpoints para auth, perfiles (incluyendo create/update/reset password admin) y LLM.

La app Streamlit ahora puede consumir backend de forma opcional con `BACKEND_API_ENABLED=true`, manteniendo fallback local para continuidad operativa.

Se agregó manejo de expiración de token con refresh preventivo/forzado, reintento tras error de autenticación y auto-logout opcional (`BACKEND_AUTO_LOGOUT_ON_AUTH_FAILURE`).

También se incorporó aviso visual en sidebar cuando backend está activo pero la sesión backend no es válida.

Validación ejecutada:
- `python -m pytest tests/test_login.py tests/test_perfil.py tests/test_utils.py -q` → 38 passed
- `python -m pytest AgenteSFTPBackend/tests -q` → 17 passed

Riesgo principal: dependencia de disponibilidad del backend cuando coexistencia está activa.
Mitigación: fallback local, refresh/retry de token y opción de rollback con `BACKEND_API_ENABLED=false`.
