from pathlib import Path


def read_agent_prompt(filename: str) -> str:
    """Lee prompt de agente desde .github/agents con fallback seguro."""
    path = Path(".github/agents") / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "Eres un asistente experto en modernizacion legacy para IBM i."
