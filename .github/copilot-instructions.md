# Reglas de Contexto del Proyecto: IBM i Legacy Agent Migrator

## Estructura de Agentes
- Todos los agentes de IA residen en `.github/agents/`.
- Cada archivo `.md` en esa carpeta define un rol específico (Analista, Arquitecto, Desarrollador, Auditor, Writer).

## Reglas de Documentación (Agente 05)
Al solicitar documentación o un README:
1. Lee siempre `.github/agents/05_writer.md`.
2. Incluye diagramas Mermaid que representen el flujo de migración de IBM i.
3. Asegúrate de que el tono sea de "Technical Writer & Full-Stack Developer".

## Reglas de Código (Agente 03)
- El destino de la migración es SIEMPRE nativo de IBM i (AS/400).
- Prohibido sugerir Python como lenguaje de destino para la lógica de migración en el servidor.
- Usa RPGLE Free-Form y comandos CL (QSH/STRQSH).