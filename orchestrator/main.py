"""
Orquestador central - YTCreator Studio
=========================================

Es el cerebro del sistema. No genera contenido el mismo: solo decide
en que orden llamar a cada departamento, valida que cada paso este
realmente completo antes de avanzar, y maneja la decision critica
mas importante del pipeline: si el guion no pasa el score minimo,
lo manda de vuelta al Guionista en vez de avanzar con un guion flojo.
"""

import sys
import time
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
MAX_REINTENTOS_AGENTE = 3
BACKOFF_BASE = 5


def _llamar(agente_id: str, proyecto_id: str, parametros: dict | None = None) -> dict:
    request = AgenteRequest(proyecto_id=proyecto_id, parametros=parametros or {})
    ultimo_error = None

    for intento in range(1, MAX_REINTENTOS_AGENTE + 1):
        try:
            resp = httpx.post(
                f"{url_agente(agente_id)}/ejecutar",
                json=request.model_dump(),
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("estado") == "error":
                raise RuntimeError(f"{agente_id} fallo: {data.get('error')}")
            return data

        except Exception as exc:
            ultimo_error = exc
            if intento < MAX_REINTENTOS_AGENTE:
                espera = BACKOFF_BASE * intento
                time.sleep(espera)

    state.actualizar(
        proyecto_id,
        errores=[f"{agente_id}: {ultimo_error} (tras {MAX_REINTENTOS_AGENTE} intentos)"],
    )
    raise RuntimeError(f"{agente_id} fallo tras {MAX_REINTENTOS_AGENTE} intentos: {ultimo_error}")


def _fase(proyecto_id: str, fase: str):
    state.actualizar(proyecto_id, fase_actual=fase)


FASES_ORDEN = ["estrategia", "guion", "visual", "audio", "cierre"]


def _fase_completada(proyecto_id: str, fase_objetivo: str) -> bool:
    """Verifica si una fase ya fue completada revisando el estado del proyecto."""
    try:
        estado = state.leer(proyecto_id)
    except FileNotFoundError:
        return False

    fase_actual_idx = FASES_ORDEN.index(estado.fase_actual) if estado.fase_actual in FASES_ORDEN else -1
    fase_objetivo_idx = FASES_ORDEN.index(fase_objetivo)

    if fase_actual_idx <= fase_objetivo_idx:
        return False

    if fase_objetivo == "estrategia":
        return bool(estado.estrategia.titulo_ganador)
    if fase_objetivo == "guion":
        return estado.guion.aprobado
    if fase_objetivo == "visual":
        return estado.visual.prompts_generados
    if fase_objetivo == "audio":
        return estado.audio.voz_path is not None
    return False


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


@app.post("/pipeline/ejecutar")
def ejecutar_pipeline(proyecto_id: str, nicho: str):
    """Corre el pipeline completo con tracking de fase, reintentos y recovery."""

    try:
        # 1. Estrategia (Investigador -> Copywriter -> Director de Arte)
        if not _fase_completada(proyecto_id, "estrategia"):
            _fase(proyecto_id, "estrategia")
            _llamar("sub_orq_estrategia", proyecto_id, {"nicho": nicho})

        # 2. Guion con loop de reescritura
        if not _fase_completada(proyecto_id, "guion"):
            _fase(proyecto_id, "guion")
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
                state.actualizar(
                    proyecto_id,
                    fase_actual="error",
                    errores=["Guion no paso el score minimo tras varios intentos"],
                )
                raise HTTPException(
                    status_code=422,
                    detail="El guion no paso el score minimo tras varios intentos de reescritura",
                )

        # 3. Visual y Audio
        if not _fase_completada(proyecto_id, "visual"):
            _fase(proyecto_id, "visual")
            _llamar("3.1_prompt_maker", proyecto_id)
            _llamar("3.2_generador_visual", proyecto_id)

        if not _fase_completada(proyecto_id, "audio"):
            _fase(proyecto_id, "audio")
            _llamar("sub_orq_audio", proyecto_id)

        # 4. Cierre (Editor Tecnico + Consultor SEO)
        _fase(proyecto_id, "cierre")
        _llamar("sub_orq_cierre", proyecto_id)

        _fase(proyecto_id, "completado")
        return state.leer(proyecto_id)

    except HTTPException:
        raise
    except Exception as exc:
        state.actualizar(
            proyecto_id,
            fase_actual="error",
            errores=[str(exc)],
        )
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES["orquestador_central"])
