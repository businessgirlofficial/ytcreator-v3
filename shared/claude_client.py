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


def analizar_miniatura_claude(imagen_url: str) -> dict:
    """
    Analiza visualmente una miniatura de YouTube usando Claude vision.
    Descarga la imagen y la pasa a Claude para extraer elementos visuales.
    """
    import base64
    import httpx as _httpx

    try:
        resp = _httpx.get(imagen_url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        imagen_bytes = resp.content
        imagen_b64 = base64.b64encode(imagen_bytes).decode("utf-8")

        content_type = resp.headers.get("content-type", "image/jpeg")
        if "png" in content_type:
            media_type = "image/png"
        elif "webp" in content_type:
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"
    except Exception as exc:
        log.warning("no se pudo descargar miniatura %s: %s", imagen_url[:80], exc)
        return {}

    system_prompt = (
        "Eres un analista visual de miniaturas de YouTube. "
        "Analiza la imagen y extrae los elementos visuales con precision. "
        "SIEMPRE respondes en JSON valido con este formato exacto:\n"
        "{\n"
        '  "colores_dominantes": ["color1", "color2", "color3"],\n'
        '  "tiene_texto_overlay": true/false,\n'
        '  "texto_overlay": "texto visible en la imagen o null",\n'
        '  "posicion_texto": "izquierda/derecha/centro/superior/inferior o null",\n'
        '  "tiene_rostro": true/false,\n'
        '  "expresion_facial": "sorpresa/serio/sonriente/enojado/pensativo o null",\n'
        '  "composicion": "descripcion de la composicion (ej: rostro a la izquierda, texto a la derecha, fondo gradiente)",\n'
        '  "contraste": "alto/medio/bajo",\n'
        '  "elementos_graficos": ["flechas", "circulos", "emojis", "bordes de color", etc],\n'
        '  "estilo_general": "descripcion del estilo visual en 1 frase (ej: minimalista oscuro con texto grande amarillo)"\n'
        "}\n"
        "Se preciso y concreto. No inventes elementos que no ves."
    )

    user_prompt = "Analiza esta miniatura de YouTube y extrae sus elementos visuales."

    try:
        CLAUDE_LIMITER.esperar()

        options = ClaudeCodeOptions(
            system_prompt=system_prompt + _SUFIJO_JSON,
            max_turns=CLAUDE_MAX_TURNS,
            model=CLAUDE_MODEL,
            allowed_tools=[],
        )

        prompt_con_imagen = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": imagen_b64,
                },
            },
            {"type": "text", "text": user_prompt},
        ]

        mensajes = []

        async def _run():
            async for msg in query(prompt=prompt_con_imagen, options=options):
                mensajes.append(msg)

        asyncio.run(_run())
        contenido = _extraer_texto(mensajes)
        return parsear_json_llm(contenido)
    except Exception as exc:
        log.warning("analisis miniatura fallo: %s", exc)
        return {}


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
