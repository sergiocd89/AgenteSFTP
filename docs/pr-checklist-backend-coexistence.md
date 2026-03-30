# PR Checklist - Backend Coexistence Phase 1

Checklist recomendado para abrir el PR de la rama de coexistencia Streamlit + FastAPI.

## 1. Alcance del PR

- [ ] Se crea el backend FastAPI en AgenteSFTPBackend con versionado /api/v1.
- [ ] Se integra auth JWT (login, refresh, cambio de contraseña).
- [ ] Se integra perfiles (lectura, acceso por módulo, create, update, reset password admin).
- [ ] Se integra endpoint LLM protegido por token.
- [ ] Streamlit consume backend de forma opcional por variables BACKEND_API_*, con fallback local.

## 2. Variables de entorno y configuración

- [ ] BACKEND_API_ENABLED configurada por ambiente.
- [ ] BACKEND_API_BASE_URL apuntando al backend correcto.
- [ ] BACKEND_AUTO_LOGOUT_ON_AUTH_FAILURE definida según política de seguridad.
- [ ] JWT_SECRET_KEY definida con longitud recomendada (>=32 bytes).
- [ ] JWT_ALGORITHM y JWT_EXP_MINUTES revisadas para ambiente objetivo.

## 3. Validación técnica mínima

- [ ] Pruebas Streamlit pasan:
  - python -m pytest tests/test_login.py tests/test_perfil.py tests/test_utils.py -q
- [ ] Pruebas de contrato backend pasan:
  - python -m pytest AgenteSFTPBackend/tests -q
- [ ] Sin errores de análisis en archivos modificados.

## 4. Riesgos conocidos

- [ ] Convivencia temporal: si BACKEND_API_ENABLED=true pero backend no está disponible, algunas rutas caerán a fallback local o mostrarán aviso de sesión backend inválida.
- [ ] Tokens expiran por diseño: validar expiración real contra UX esperada.
- [ ] Confirmar consistencia de perfiles cuando se alterna entre proveedor local y backend.

## 5. Rollback

- [ ] Opción rápida: deshabilitar BACKEND_API_ENABLED=false para volver a flujo local Streamlit.
- [ ] Mantener rama main sin cambios de coexistencia hasta aprobación final.
- [ ] Verificar que variables nuevas no bloqueen despliegue legacy.

## 6. Evidencia para PR

Adjuntar en la descripción del PR:

- [ ] Captura de pantalla de login y sidebar con sesión backend activa.
- [ ] Captura de error controlado cuando token backend expira.
- [ ] Resultado de pruebas ejecutadas (comandos y conteo de tests).
- [ ] Lista de endpoints nuevos añadidos en backend.

## 7. Criterios de aprobación

- [ ] Equipo backend valida contratos y seguridad básica JWT.
- [ ] Equipo frontend valida UX de coexistencia y fallback.
- [ ] Aprobación funcional de login, perfiles y LLM en ambiente de prueba.
- [ ] Plan de despliegue faseado aceptado.
