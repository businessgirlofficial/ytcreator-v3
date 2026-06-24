"""
Sub-orquestador - Depto 5 (Cierre)

Coordina: Editor Tecnico (5.1) -> Consultor SEO (5.2) -> Compliance (5.3)

El agente de Compliance (5.3) es la ultima puerta del pipeline. Si
detecta nivel_riesgo "critico", el sub-orquestador bloquea la
finalizacion del video. Niveles "alto", "medio" y "bajo" pasan con
sus respectivos warnings en el estado.

El agente 5.4 (Policy Monitor) NO se ejecuta aqui — corre por fuera
del pipeline (via n8n semanal o manualmente).
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
from shared.state_manager import StateManager

AGENTE_ID = "sub_orq_cierre"
app: FastAPI = crear_agente_app(
    AGENTE_ID, descripcion="Orquesta Editor Tecnico, Consultor SEO y Compliance YouTube"
)

SECUENCIA = ["5.1_editor", "5.2_seo", "5.3_compliance", "5.5_publicador"]
state = StateManager()


def _subpaso_completado(proyecto_id: str, agente_id: str) -> bool:
    try:
        estado = state.leer(proyecto_id)
    except FileNotFoundError:
        return False
    if agente_id == "5.1_editor":
        return estado.video_final_path is not None
    if agente_id == "5.2_seo":
        return estado.metadata.descripcion is not None
    if agente_id == "5.3_compliance":
        return estado.compliance.aprobado is not None
    if agente_id == "5.5_publicador":
        return estado.publicado
    return False


def logica(request: AgenteRequest) -> dict:
    resultados = {}

    for agente_id in ["5.1_editor", "5.2_seo", "5.3_compliance"]:
        if _subpaso_completado(request.proyecto_id, agente_id):
            continue
        data = llamar_con_reintento(agente_id, request)
        resultados[agente_id] = data

    estado = state.leer(request.proyecto_id)
    nivel_riesgo = estado.compliance.nivel_riesgo or "bajo"
    compliance_aprobado = estado.compliance.aprobado if estado.compliance.aprobado is not None else True

    if nivel_riesgo == "critico":
        raise RuntimeError(
            f"Compliance YouTube BLOQUEO el video: "
            f"{estado.compliance.resumen or 'riesgo critico detectado'}"
        )

    if not _subpaso_completado(request.proyecto_id, "5.5_publicador"):
        try:
            data = llamar_con_reintento("5.5_publicador", request)
            resultados["5.5_publicador"] = data
        except Exception:
            resultados["5.5_publicador"] = {"output": {"publicado": False, "skipped_reason": "agente no disponible"}}

    estado = state.leer(request.proyecto_id)

    return {
        "compliance_aprobado": compliance_aprobado,
        "compliance_nivel_riesgo": nivel_riesgo,
        "compliance_warnings": estado.compliance.warnings,
        "publicado": estado.publicado,
        "youtube_video_id": estado.youtube_video_id,
        "youtube_url": f"https://youtu.be/{estado.youtube_video_id}" if estado.youtube_video_id else None,
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
