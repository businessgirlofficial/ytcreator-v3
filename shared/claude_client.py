"""
Cliente Claude (Code SDK) - YTCreator Studio
===============================================

Wrapper sobre claude-code-sdk para generacion de JSON.
Autentica con la suscripcion Claude Pro del usuario via CLI.

Prerequisito: tener Claude Code instalado y autenticado:
  npm install -g @anthropic-ai/claude-code && claude login
"""

import asyncio
import json

from claude_code_sdk import (
    AssistantMessage,
    ClaudeCodeOptions,
    TextBlock,
    query,
)

from .config import CLAUDE_MAX_TURNS, CLAUDE_MODEL
from .groq_client import _sanitizar_prompt, parsear_json_llm
from .logger import get_logger
from .rate_limiter import CLAUDE_LIMITER

log = get_logger("claude_client")

_SUFIJO_JSON = (
    "\n\nIMPORTANTE: Responde SOLO con JSON valido. "
    "No incluyas texto, explicaciones ni code fences antes o despues del JSON. "
    "Solo el JSON puro."
)


def _extraer_texto(mensajes: list) -> str:
    partes = []
    for msg in mensajes:
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    partes.append(block.text)
    return "\n".join(partes)


async def _query_claude(system_prompt: str, user_prompt: str) -> str:
    options = ClaudeCodeOptions(
        system_prompt=system_prompt + _SUFIJO_JSON,
        max_turns=CLAUDE_MAX_TURNS,
        model=CLAUDE_MODEL,
        allowed_tools=[],
    )
    mensajes = []
    async for message in query(prompt=user_prompt, options=options):
        mensajes.append(message)
    return _extraer_texto(mensajes)


def generar_json_claude(
    system_prompt: str,
    user_prompt: str,
    intentos: int = 2,
) -> dict:
    """
    Genera JSON usando Claude (Code SDK).
    Misma filosofia que generar_json() de groq_client.
    """
    ultimo_error: Exception | None = None
    user_prompt_limpio = _sanitizar_prompt(user_prompt)

    for intento in range(intentos):
        try:
            CLAUDE_LIMITER.esperar()
            contenido = asyncio.run(
                _query_claude(system_prompt, user_prompt_limpio)
            )
            return parsear_json_llm(contenido)
        except Exception as exc:
            ultimo_error = exc
            log.warning(
                "Claude intento %d/%d fallo: %s", intento + 1, intentos, exc
            )

    raise RuntimeError(f"Claude fallo tras {intentos} intento(s): {ultimo_error}")


def revisar_con_claude(
    json_original: dict,
    review_prompt: str,
    system_prompt: str = "",
) -> dict:
    """
    Envia un JSON a Claude para revision/mejora.
    Retorna el JSON corregido o el original si Claude falla.
    """
    if not system_prompt:
        system_prompt = (
            "Eres un revisor de calidad experto en produccion visual para YouTube. "
            "Recibes un JSON y un contexto de revision. "
            "Si el JSON necesita mejoras, devuelve el JSON corregido. "
            "Si ya es bueno, devuelvelo sin cambios."
        )

    user_completo = f"""{review_prompt}

JSON a revisar:
{json.dumps(json_original, ensure_ascii=False, indent=2)}"""

    try:
        return generar_json_claude(system_prompt, user_completo, intentos=1)
    except Exception as exc:
        log.warning("Revision Claude fallo, usando original: %s", exc)
        return json_original
