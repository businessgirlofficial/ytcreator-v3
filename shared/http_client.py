"""
Cliente HTTP compartido con reintentos - YTCreator Studio
============================================================

Funcion unica de llamada a agentes con retry + backoff + logging.
Todos los sub-orquestadores usan esto en vez de copiar la logica.
"""

import time

import httpx

from .config import url_agente
from .logger import get_logger
from .schemas import AgenteRequest

log = get_logger("http_client")

MAX_REINTENTOS = 3
BACKOFF_BASE = 5


def llamar_con_reintento(
    agente_id: str,
    request: AgenteRequest,
    timeout: int = 180,
    max_reintentos: int = MAX_REINTENTOS,
) -> dict:
    ultimo_error = None
    for intento in range(1, max_reintentos + 1):
        try:
            resp = httpx.post(
                f"{url_agente(agente_id)}/ejecutar",
                json=request.model_dump(),
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("estado") == "error":
                raise RuntimeError(f"{agente_id} fallo: {data.get('error')}")
            log.info("ok %s | proyecto=%s | intento=%d", agente_id, request.proyecto_id, intento)
            return data
        except Exception as exc:
            ultimo_error = exc
            if intento < max_reintentos:
                espera = BACKOFF_BASE * intento
                log.warning(
                    "reintento %d/%d %s | proyecto=%s | error=%s",
                    intento, max_reintentos, agente_id, request.proyecto_id, exc,
                )
                time.sleep(espera)

    log.error("fallo %s | proyecto=%s | tras %d intentos | %s", agente_id, request.proyecto_id, max_reintentos, ultimo_error)
    raise RuntimeError(f"{agente_id} fallo tras {max_reintentos} intentos: {ultimo_error}")
