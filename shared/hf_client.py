"""
Cliente HuggingFace compartido - YTCreator Studio
====================================================

Wrapper sobre la Inference API de HuggingFace con rate limiting
integrado. Centraliza la logica de cold start (503), rate limit
(429) y reintentos para que los agentes no la repitan.

Lo usan:
  - Agente 1.4 (Generador de miniatura) → FLUX.1-schnell
  - Agente 4.2 (Productor musical) → MusicGen
  - Sub-orquestador Visual → LLaVA
"""

import time

import httpx

from .config import HF_API_TOKEN, MAX_IMAGEN_BYTES
from .logger import get_logger
from .rate_limiter import HF_LIMITER

log = get_logger("hf_client")

HF_MAX_ESPERA_CARGA = 120
HF_POLL_INTERVAL = 10


def llamar_modelo(
    url: str,
    payload: dict,
    timeout: int = 180,
    max_espera_carga: int = HF_MAX_ESPERA_CARGA,
    max_bytes: int = MAX_IMAGEN_BYTES,
) -> httpx.Response:
    """
    Llama a un modelo de HF Inference API con rate limiting, manejo de
    cold start (503), error claro en rate limit (429), y validacion de
    tamaño maximo de respuesta.

    Devuelve el httpx.Response exitoso para que el agente procese el
    contenido segun el tipo de modelo (imagen, audio, JSON, etc).
    """
    if not HF_API_TOKEN:
        raise RuntimeError(
            "HF_API_TOKEN no esta configurada. Generala gratis en "
            "huggingface.co/settings/tokens"
        )

    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    esperado = 0

    while esperado < max_espera_carga:
        HF_LIMITER.esperar()

        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)

        if resp.status_code == 503:
            body = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else {}
            )
            wait = min(body.get("estimated_time", HF_POLL_INTERVAL), 30)
            log.info("modelo cargando %s | esperando %ds", url.split("/")[-1], wait)
            time.sleep(wait)
            esperado += wait
            continue

        if resp.status_code == 429:
            raise RuntimeError(
                f"HuggingFace rate limit alcanzado para {url.split('/')[-1]}"
            )

        resp.raise_for_status()

        content_length = resp.headers.get("content-length")
        size = int(content_length) if content_length else len(resp.content)
        if size > max_bytes:
            raise RuntimeError(
                f"Respuesta de {url.split('/')[-1]} excede el limite: "
                f"{size / 1024 / 1024:.1f}MB > {max_bytes / 1024 / 1024:.0f}MB"
            )

        return resp

    raise RuntimeError(
        f"El modelo {url.split('/')[-1]} no termino de cargar "
        f"tras {max_espera_carga}s"
    )
