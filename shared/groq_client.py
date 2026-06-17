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

from groq import Groq

from .config import GROQ_API_KEY

MODELO_DEFAULT = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

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

    for _ in range(intentos):
        try:
            respuesta = cliente.chat.completions.create(
                model=modelo,
                temperature=temperatura,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            contenido = respuesta.choices[0].message.content
            return _parsear_json(contenido)
        except Exception as exc:  # noqa: BLE001 - queremos capturar y reintentar cualquier falla
            ultimo_error = exc

    raise RuntimeError(f"Groq fallo tras {intentos} intento(s): {ultimo_error}")


def _parsear_json(contenido: str) -> dict:
    try:
        return json.loads(contenido)
    except json.JSONDecodeError:
        inicio = contenido.find("{")
        fin = contenido.rfind("}")
        if inicio != -1 and fin != -1 and fin > inicio:
            return json.loads(contenido[inicio : fin + 1])
        raise ValueError(f"Groq no devolvio JSON valido. Respuesta cruda: {contenido[:300]}")
