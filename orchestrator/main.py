"""
Orquestador central - YTCreator Studio
=========================================

Es el cerebro del sistema. No genera contenido el mismo: solo decide
en que orden llamar a cada departamento, valida que cada paso este
realmente completo antes de avanzar, y maneja la decision critica
mas importante del pipeline: si el guion no pasa el score minimo,
lo manda de vuelta al Guionista en vez de avanzar con un guion flojo.

Este archivo es el ESQUELETO de la Fase 0. La logica de reintentos
mas fina, el paralelismo real entre Visual y Audio, y el manejo
detallado de errores se completan en la Fase 6 del roadmap (cuando
ya todos los departamentos esten probados por separado).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException

from shared.config import REGISTRO_AGENTES, url_agente
from shared.schemas import AgenteRequest
from shared.state_manager import StateManager

app = FastAPI(title="Orquestador Central - YTCreator Studio")
state = StateManager()

MAX_REINTENTOS_GUION = 3


@app.get("/health")
def health():
    return {"servicio": "orquestador_central", "estado": "ok"}


@app.post("/proyectos")
def crear_proyecto(proyecto_id: str, canal: str):
    try:
        return state.crear(proyecto_id, canal)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/proyectos/{proyecto_id}")
def leer_proyecto(proyecto_id: str):
    try:
        return state.leer(proyecto_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/proyectos")
def listar_proyectos():
    return {"proyectos": state.listar_proyectos()}


def _llamar(agente_id: str, proyecto_id: str, parametros: dict | None = None) -> dict:
    request = AgenteRequest(proyecto_id=proyecto_id, parametros=parametros or {})
    resp = httpx.post(f"{url_agente(agente_id)}/ejecutar", json=request.model_dump(), timeout=300)
    resp.raise_for_status()
    data = resp.json()
    if data.get("estado") == "error":
        raise RuntimeError(f"{agente_id} fallo: {data.get('error')}")
    return data


@app.post("/pipeline/ejecutar")
def ejecutar_pipeline(proyecto_id: str, nicho: str):
    """Corre el pipeline completo de punta a punta para un proyecto ya creado."""

    # 1. Estrategia (Investigador -> Copywriter -> Director de Arte)
    _llamar("sub_orq_estrategia", proyecto_id, {"nicho": nicho})

    # 2. Guion con loop de reescritura -- la decision critica del orquestador
    intentos = 0
    aprobado = False
    while intentos < MAX_REINTENTOS_GUION:
        _llamar("2.1_guionista", proyecto_id)
        _llamar("2.2_evaluador", proyecto_id)
        estado_actual = state.leer(proyecto_id)
        if estado_actual.guion.aprobado:
            aprobado = True
            break
        intentos += 1

    if not aprobado:
        raise HTTPException(
            status_code=422,
            detail="El guion no paso el score minimo tras varios intentos de reescritura",
        )

    # 3. Visual y Audio -- secuencial en Fase 0, paralelizable en Fase 6
    _llamar("3.1_prompt_maker", proyecto_id)
    _llamar("3.2_generador_visual", proyecto_id)
    _llamar("sub_orq_audio", proyecto_id)

    # 4. Cierre (Editor Tecnico + Consultor SEO)
    _llamar("sub_orq_cierre", proyecto_id)

    return state.leer(proyecto_id)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES["orquestador_central"])
