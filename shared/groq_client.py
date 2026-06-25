"""
Cliente Groq compartido - YTCreator Studio
=============================================

Wrapper minimo sobre la API de Groq para que los agentes no repitan
la logica de llamada, parseo de JSON y reintentos. Usa por defecto el
modelo Llama 3.3 70B (el mismo que ya usas en el notebook v7).

Si Groq cambia su catalogo de modelos, ajusta GROQ_MODEL en tu .env
en vez de tocar este archivo o cada agente.
"""

import json
import os
import re

from groq import Groq

from .config import GROQ_API_KEY
from .rate_limiter import GROQ_LIMITER

MODELO_DEFAULT = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_PATRONES_INYECCION = [
    re.compile(
        r"(?i)(ignore|ignora|olvida|forget|disregard)"
        r"\s+(todo|all|everything|las instrucciones|the instructions|lo anterior|above)",
    ),
    re.compile(r"(?i)(nuevas?\s+instrucciones|new\s+instructions)"),
    re.compile(r"(?i)(system\s*prompt|eres\s+ahora|you\s+are\s+now|act\s+as)"),
    re.compile(r"<\s*/?\s*(system|user|assistant|instrucciones|prompt)\s*/?\s*>", re.IGNORECASE),
]


def _sanitizar_prompt(texto: str) -> str:
    """Neutraliza patrones comunes de prompt injection en inputs de usuario."""
    limpio = texto.replace("\r\n", "\n")
    limpio = re.sub(r"-{3,}", "--", limpio)
    limpio = re.sub(r"#{3,}", "##", limpio)
    for patron in _PATRONES_INYECCION:
        limpio = patron.sub("[FILTERED]", limpio)
    return limpio

_cliente: Groq | None = None


def _get_cliente() -> Groq:
    global _cliente
    if _cliente is None:
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY no esta configurada. Revisa tu archivo .env "
                "(copialo desde .env.example si no existe)."
            )
        _cliente = Groq(api_key=GROQ_API_KEY)
    return _cliente


def generar_json(
    system_prompt: str,
    user_prompt: str,
    modelo: str = MODELO_DEFAULT,
    temperatura: float = 0.8,
    intentos: int = 2,
) -> dict:
    """
    Llama a Groq pidiendo una respuesta JSON valida. Reintenta si el
    modelo devuelve un JSON mal formado (pasa de vez en cuando con
    LLMs, incluso pidiendo response_format json_object).
    """
    cliente = _get_cliente()
    ultimo_error: Exception | None = None

    user_prompt_limpio = _sanitizar_prompt(user_prompt)

    for _ in range(intentos):
        try:
            GROQ_LIMITER.esperar()
            respuesta = cliente.chat.completions.create(
                model=modelo,
                temperature=temperatura,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt_limpio},
                ],
            )
            contenido = respuesta.choices[0].message.content
            return _parsear_json(contenido)
        except Exception as exc:  # noqa: BLE001 - queremos capturar y reintentar cualquier falla
            ultimo_error = exc

    raise RuntimeError(f"Groq fallo tras {intentos} intento(s): {ultimo_error}")


def parsear_json_llm(contenido: str) -> dict:
    """
    Parseo robusto de JSON desde respuestas LLM con 3 capas de fallback:
      1. json.loads directo (fast path, funciona ~90% del tiempo)
      2. Strip code fences + json.loads
      3. Extraccion balanceada del primer bloque JSON completo

    La capa 4 (reintentar la llamada al LLM) la maneja generar_json()
    con su loop de intentos.

    Publica para que otros modulos la reusen (ej. sub_orq_visual con LLaVA).
    """
    # Capa 1: directo
    try:
        return json.loads(contenido)
    except (json.JSONDecodeError, ValueError):
        pass

    # Capa 2: strip code fences (```json ... ``` o ``` ... ```)
    sin_fences = re.sub(r"```(?:json)?\s*\n?", "", contenido).strip()
    try:
        return json.loads(sin_fences)
    except (json.JSONDecodeError, ValueError):
        pass

    # Capa 3: extraccion balanceada del primer {...} o [...]
    bloque = _extraer_json_balanceado(contenido)
    if bloque is not None:
        try:
            return json.loads(bloque)
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(f"No se pudo extraer JSON valido. Respuesta cruda: {contenido[:300]}")


def _extraer_json_balanceado(texto: str) -> str | None:
    """Encuentra el primer bloque JSON ({...} o [...]) con llaves balanceadas."""
    for char_abre, char_cierra in [("{", "}"), ("[", "]")]:
        inicio = texto.find(char_abre)
        if inicio == -1:
            continue

        profundidad = 0
        en_string = False
        escape = False

        for i in range(inicio, len(texto)):
            c = texto[i]

            if escape:
                escape = False
                continue

            if c == "\\":
                escape = True
                continue

            if c == '"' and not escape:
                en_string = not en_string
                continue

            if en_string:
                continue

            if c == char_abre:
                profundidad += 1
            elif c == char_cierra:
                profundidad -= 1
                if profundidad == 0:
                    return texto[inicio : i + 1]

    return None


# Alias interno para compatibilidad
_parsear_json = parsear_json_llm
