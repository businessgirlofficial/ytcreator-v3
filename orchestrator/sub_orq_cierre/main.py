"""
Sub-orquestador - Depto 5 (Cierre)

Coordina: Editor Tecnico (5.1) -> Consultor SEO (5.2).
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

AGENTE_ID = "sub_orq_cierre"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Orquesta Editor Tecnico y Consultor SEO")

SECUENCIA = ["5.1_editor", "5.2_seo"]
MAX_REINTENTOS = 3
BACKOFF_BASE = 5


def _llamar_con_reintento(agente_id: str, request: AgenteRequest) -> dict:
    ultimo_error = None
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            resp = httpx.post(
                f"{url_agente(agente_id)}/ejecutar",
                json=request.model_dump(),
                timeout=180,
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
