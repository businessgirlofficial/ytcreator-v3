"""
Sub-orquestador - Depto 0 (Inteligencia de Canal)

Dos modos de operacion:

  Modo A (escaneo completo):
    0.1 Escaner -> 0.2 Analizador -> 0.3 Monitor Mercado -> 0.4 Asesor

  Modo B (quick refresh):
    Si los datos del canal tienen < 24h, solo re-ejecuta 0.4 (Asesor).
    Si estan viejos, ejecuta Modo A completo.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.channel_manager import ChannelManager
from shared.config import REGISTRO_AGENTES
from shared.http_client import llamar_con_reintento
from shared.logger import get_logger
from shared.schemas import AgenteRequest, AgenteResponse

AGENTE_ID = "sub_orq_inteligencia"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Orquesta el pipeline de inteligencia de canal")
channels = ChannelManager()
log = get_logger(AGENTE_ID)

SECUENCIA_COMPLETA = [
    "0.1_escaner_canal",
    "0.2_analizador_canal",
    "0.3_monitor_mercado",
    "0.4_asesor_estrategico",
]


def logica(request: AgenteRequest) -> dict:
    canal_id = request.parametros.get("canal_id", "")
    canal_input = request.parametros.get("canal_input", "")
    modo = request.parametros.get("modo", "completo")

    if not canal_id and not canal_input:
        raise ValueError("Falta 'canal_id' o 'canal_input' en parametros")

    if modo == "quick_refresh" and canal_id:
        necesita_refresco = channels.canal_necesita_refresco(canal_id)
        if not necesita_refresco:
            log.info("canal %s esta fresco, solo re-ejecutando asesor", canal_id)
            req_asesor = AgenteRequest(
                proyecto_id=request.proyecto_id,
                parametros={"canal_id": canal_id},
            )
            data = llamar_con_reintento("0.4_asesor_estrategico", req_asesor, timeout=120)
            return {"modo": "quick_refresh", "asesor": data, "canal_id": canal_id}

    resultados = {}

    req_escaner = AgenteRequest(
        proyecto_id=request.proyecto_id,
        parametros={"canal_input": canal_input or canal_id},
    )
    data_escaner = llamar_con_reintento("0.1_escaner_canal", req_escaner, timeout=120)
    resultados["0.1_escaner_canal"] = data_escaner

    canal_id_resuelto = (
        data_escaner.get("output", {}).get("canal_id")
        or canal_id
    )

    for agente_id in SECUENCIA_COMPLETA[1:]:
        req = AgenteRequest(
            proyecto_id=request.proyecto_id,
            parametros={"canal_id": canal_id_resuelto},
        )
        data = llamar_con_reintento(agente_id, req, timeout=120)
        resultados[agente_id] = data

    return {
        "modo": "completo",
        "canal_id": canal_id_resuelto,
        "resultados": resultados,
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
