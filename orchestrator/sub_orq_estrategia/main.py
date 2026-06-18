"""
Sub-orquestador - Depto 1 (Estrategia)

Coordina, en orden: Investigador (1.1) -> Copywriter (1.2) -> Director
de Arte (1.3). Cada agente lee y escribe el mismo proyecto_id en el
estado compartido, asi que este sub-orquestador NO necesita pasar
datos manualmente entre ellos - solo dispara cada paso en orden y
verifica que no haya fallado antes de seguir.
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import httpx
import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES, url_agente
from shared.schemas import AgenteRequest, AgenteResponse

AGENTE_ID = "sub_orq_estrategia"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Orquesta Investigador, Copywriter y Director de Arte")

SECUENCIA = ["1.1_investigador", "1.2_copywriter", "1.3_director_arte", "1.4_generador_miniatura"]
MAX_REINTENTOS = 3
BACKOFF_BASE = 5


def _llamar_con_reintento(agente_id: str, request: AgenteRequest) -> dict:
    ultimo_error = None
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            resp = httpx.post(
                f"{url_agente(agente_id)}/ejecutar",
                json=request.model_dump(),
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("estado") == "error":
                raise RuntimeError(f"{agente_id} fallo: {data.get('error')}")
            return data
        except Exception as exc:
            ultimo_error = exc
            if intento < MAX_REINTENTOS:
                time.sleep(BACKOFF_BASE * intento)
    raise RuntimeError(f"{agente_id} fallo tras {MAX_REINTENTOS} intentos: {ultimo_error}")


def logica(request: AgenteRequest) -> dict:
    resultados = {}
    for agente_id in SECUENCIA:
        data = _llamar_con_reintento(agente_id, request)
        resultados[agente_id] = data
    return resultados


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
