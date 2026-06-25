"""
Cargador de knowledge base para agentes - YTCreator Studio
=============================================================

Carga archivos de conocimiento desde knowledge/departamentos/ para
inyectarlos en el user_prompt de cada agente. Cada agente carga
SOLO el archivo de su departamento.

Estructura esperada:
    knowledge/
    ├── departamentos/
    │   ├── depto_0_inteligencia.md
    │   ├── depto_1_estrategia.md
    │   ├── depto_2_guion.md
    │   ├── depto_3_visual.md
    │   └── depto_5_cierre.md
    └── youtube_policies.md
"""

from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"
DEPARTAMENTOS_DIR = KNOWLEDGE_DIR / "departamentos"

_cache: dict[str, str] = {}


def cargar_knowledge(departamento: str) -> str:
    """Carga el archivo de knowledge de un departamento.

    Args:
        departamento: nombre del archivo sin extensión
            (ej: "depto_0_inteligencia", "depto_1_estrategia")

    Returns:
        Contenido del archivo markdown, o cadena vacía si no existe.
    """
    if departamento in _cache:
        return _cache[departamento]

    path = DEPARTAMENTOS_DIR / f"{departamento}.md"
    if not path.exists():
        return ""

    contenido = path.read_text(encoding="utf-8")
    _cache[departamento] = contenido
    return contenido


def cargar_politicas() -> str:
    """Carga youtube_policies.md (para compliance)."""
    if "youtube_policies" in _cache:
        return _cache["youtube_policies"]

    path = KNOWLEDGE_DIR / "youtube_policies.md"
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontro {path}. El archivo de politicas es requerido."
        )

    contenido = path.read_text(encoding="utf-8")
    _cache["youtube_policies"] = contenido
    return contenido


def inyectar_knowledge(user_prompt: str, departamento: str) -> str:
    """Agrega el knowledge del departamento al final del user_prompt.

    Si el archivo no existe, retorna el user_prompt sin cambios.
    """
    knowledge = cargar_knowledge(departamento)
    if not knowledge:
        return user_prompt

    return f"""{user_prompt}

CONOCIMIENTO ESPECIALIZADO (estrategias probadas de cursos de YouTube):
{knowledge}

Usa este conocimiento como referencia para fundamentar tus decisiones,
pero prioriza siempre los datos reales del canal cuando esten disponibles."""
