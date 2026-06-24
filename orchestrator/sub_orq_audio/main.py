"""
Sub-orquestador - Depto 4 (Audio)

Coordina: Director de Locucion (4.1) -> Productor Musical (4.2) ->
Tecnico de Subtitulos (4.3).

El orden importa por una dependencia real: el Tecnico de Subtitulos
(4.3) necesita el voz.mp3 que genera 4.1, asi que no puede correr
antes. El Productor Musical (4.2) es independiente de los otros dos.
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

AGENTE_ID = "sub_orq_audio"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Orquesta Locucion, Musica y Subtitulos")

SECUENCIA = ["4.1_locucion", "4.2_musica", "4.3_subtitulos"]


def logica(request: AgenteRequest) -> dict:
    resultados = {}
    for agente_id in SECUENCIA:
        data = llamar_con_reintento(agente_id, request)
        resultados[agente_id] = data
    return resultados


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
