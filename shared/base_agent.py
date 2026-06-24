"""
Plantilla base para todos los agentes - YTCreator Studio
===========================================================

Cada microservicio (agente) usa esta plantilla para no repetir:
  - la app de FastAPI
  - el endpoint /health (para que el orquestador sepa si esta vivo)
  - el manejo estandar de errores y tiempos de ejecucion
  - el formato de respuesta (AgenteResponse)

Un agente NUEVO solo necesita escribir SU logica especifica (una
funcion que recibe AgenteRequest y devuelve un dict) - todo lo demas
ya esta resuelto aqui. Mira agents/agent_1_1_investigador/main.py
para ver el patron completo de uso.
"""

import time
from typing import Callable

from fastapi import FastAPI

from .logger import get_logger
from .schemas import AgenteRequest, AgenteResponse


def crear_agente_app(agente_id: str, descripcion: str = "", version: str = "0.1.0") -> FastAPI:
    app = FastAPI(title=f"Agente {agente_id}", description=descripcion, version=version)

    @app.get("/health")
    def health():
        return {"agente_id": agente_id, "estado": "ok"}

    return app


def envolver_logica(
    agente_id: str, logica: Callable[[AgenteRequest], dict]
) -> Callable[[AgenteRequest], AgenteResponse]:
    """
    Envuelve la funcion de logica de un agente con manejo de errores,
    medicion de tiempo y formato estandar de respuesta. Asi ningun
    agente individual tiene que reimplementar try/except ni timers.
    """

    logger = get_logger(agente_id)

    def ejecutar(request: AgenteRequest) -> AgenteResponse:
        inicio = time.time()
        logger.info("inicio | proyecto=%s", request.proyecto_id)
        try:
            output = logica(request)
            duracion = round(time.time() - inicio, 2)
            logger.info("completado | proyecto=%s | duracion=%.2fs", request.proyecto_id, duracion)
            return AgenteResponse(
                agente_id=agente_id,
                estado="completado",
                output=output,
                duracion_seg=duracion,
            )
        except Exception as exc:
            duracion = round(time.time() - inicio, 2)
            logger.error("error | proyecto=%s | duracion=%.2fs | %s", request.proyecto_id, duracion, exc, exc_info=True)
            return AgenteResponse(
                agente_id=agente_id,
                estado="error",
                error=str(exc),
                duracion_seg=duracion,
            )

    return ejecutar
