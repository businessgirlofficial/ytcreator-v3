"""
Sub-orquestador - Depto 4 (Audio)

Coordina: Director de Locucion (4.1) -> Productor Musical (4.2) ->
Tecnico de Subtitulos (4.3).

El orden importa por una dependencia real: el Tecnico de Subtitulos
(4.3) necesita el voz.mp3 que genera 4.1, asi que no puede correr
antes. El Productor Musical (4.2) es independiente de los otros dos
y podria correr en paralelo con 4.1 - se deja secuencial aqui en la
Fase 0 por simplicidad; la paralelizacion real es una mejora de la
Fase 6 (cuando el orquestador central maneje concurrencia).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import httpx
import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES, url_agente
from shared.schemas import AgenteRequest, AgenteResponse

AGENTE_ID = "sub_orq_audio"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Orquesta Locucion, Musica y Subtitulos")

# 4.3 depende del output de 4.1, por eso va despues en la secuencia.
SECUENCIA = ["4.1_locucion", "4.2_musica", "4.3_subtitulos"]


def logica(request: AgenteRequest) -> dict:
    resultados = {}
    for agente_id in SECUENCIA:
        resp = httpx.post(
            f"{url_agente(agente_id)}/ejecutar",
            json=request.model_dump(),
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        resultados[agente_id] = data
        if data.get("estado") == "error":
            raise RuntimeError(f"{agente_id} fallo: {data.get('error')}")
    return resultados


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
