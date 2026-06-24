"""
Sub-orquestador - Depto 1 (Estrategia)

Coordina, en orden: Investigador (1.1) -> Copywriter (1.2) -> Director
de Arte (1.3). Cada agente lee y escribe el mismo proyecto_id en el
estado compartido, asi que este sub-orquestador NO necesita pasar
datos manualmente entre ellos - solo dispara cada paso en orden y
verifica que no haya fallado antes de seguir.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES
from shared.http_client import llamar_con_reintento
from shared.schemas import AgenteRequest, AgenteResponse

AGENTE_ID = "sub_orq_estrategia"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Orquesta Investigador, Copywriter y Director de Arte")

SECUENCIA = ["1.1_investigador", "1.2_copywriter", "1.3_director_arte", "1.4_generador_miniatura"]


def logica(request: AgenteRequest) -> dict:
    resultados = {}
    for agente_id in SECUENCIA:
        data = llamar_con_reintento(agente_id, request, timeout=120)
        resultados[agente_id] = data
    return resultados


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
