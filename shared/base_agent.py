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
import traceback
from typing import Callable

from fastapi import FastAPI

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

    def ejecutar(request: AgenteRequest) -> AgenteResponse:
        inicio = time.time()
        try:
            output = logica(request)
            return AgenteResponse(
                agente_id=agente_id,
                estado="completado",
                output=output,
                duracion_seg=round(time.time() - inicio, 2),
            )
        except Exception as exc:
            traceback.print_exc()
            return AgenteResponse(
                agente_id=agente_id,
                estado="error",
                error=str(exc),
                duracion_seg=round(time.time() - inicio, 2),
            )

    return ejecutar
