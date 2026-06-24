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
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException

from shared.config import REGISTRO_AGENTES, url_agente
from shared.health_checks import HealthCheckError, validar_fase, validar_todo
from shared.schemas import AgenteRequest
from shared.state_manager import StateManager

app = FastAPI(title="Orquestador Central - YTCreator Studio")
state = StateManager()

MAX_REINTENTOS_AGENTE = 3
BACKOFF_BASE = 5


def _llamar(agente_id: str, proyecto_id: str, parametros: dict | None = None) -> dict:
    request = AgenteRequest(proyecto_id=proyecto_id, parametros=parametros or {})
    ultimo_error = None
    inicio = datetime.utcnow()

    state.actualizar(proyecto_id, agente_actual=agente_id)

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

            duracion = round((datetime.utcnow() - inicio).total_seconds(), 2)
            state.registrar_resultado_agente(proyecto_id, {
                "agente_id": agente_id,
                "estado": "completado",
                "intentos": intento,
                "inicio": inicio.isoformat(),
                "fin": datetime.utcnow().isoformat(),
                "duracion_seg": duracion,
            })
            state.actualizar(proyecto_id, agente_actual=None)
            return data

        except Exception as exc:
            ultimo_error = exc
            if intento < MAX_REINTENTOS_AGENTE:
                espera = BACKOFF_BASE * intento
                time.sleep(espera)

    duracion = round((datetime.utcnow() - inicio).total_seconds(), 2)
    state.registrar_resultado_agente(proyecto_id, {
        "agente_id": agente_id,
        "estado": "error",
        "intentos": MAX_REINTENTOS_AGENTE,
        "inicio": inicio.isoformat(),
        "fin": datetime.utcnow().isoformat(),
        "duracion_seg": duracion,
        "error": str(ultimo_error),
    })
    state.actualizar(
        proyecto_id,
        agente_actual=None,
        errores=[f"{agente_id}: {ultimo_error} (tras {MAX_REINTENTOS_AGENTE} intentos)"],
    )
    raise RuntimeError(f"{agente_id} fallo tras {MAX_REINTENTOS_AGENTE} intentos: {ultimo_error}")


def _fase(proyecto_id: str, fase: str):
    state.actualizar(proyecto_id, fase_actual=fase)


FASES_ORDEN = ["estrategia", "guion", "visual", "audio", "cierre", "completado", "publicado"]


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
    if fase_objetivo == "cierre":
        return estado.video_final_path is not None and estado.compliance.aprobado is not None
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
def ejecutar_pipeline(proyecto_id: str, nicho: str, canal: str = "mi_canal"):
    """Corre el pipeline completo con tracking de fase, reintentos y recovery."""

    try:
        # 0. Crear proyecto si no existe
        try:
            state.leer(proyecto_id)
        except FileNotFoundError:
            state.crear(proyecto_id, canal)

        # 0.1 Validar TODAS las credenciales antes de gastar un solo segundo
        try:
            validar_todo()
        except HealthCheckError as exc:
            state.actualizar(
                proyecto_id,
                fase_actual="error",
                errores=[f"Pre-check: {f}" for f in exc.fallos],
            )
            raise HTTPException(status_code=422, detail=str(exc))

        # 1. Estrategia (Investigador -> Copywriter -> Director de Arte)
        if not _fase_completada(proyecto_id, "estrategia"):
            validar_fase("estrategia")
            _fase(proyecto_id, "estrategia")
            _llamar("sub_orq_estrategia", proyecto_id, {"nicho": nicho})

        # 2. Guion (Sub-orquestador maneja loop escritura/evaluacion/reescritura)
        if not _fase_completada(proyecto_id, "guion"):
            validar_fase("guion")
            _fase(proyecto_id, "guion")
            resultado_guion = _llamar("sub_orq_guion", proyecto_id)
            output = resultado_guion.get("output", {})
            if not output.get("aprobado"):
                state.actualizar(
                    proyecto_id,
                    fase_actual="error",
                    errores=["Guion no paso el score minimo tras varios intentos"],
                )
                raise HTTPException(
                    status_code=422,
                    detail="El guion no paso el score minimo tras varios intentos de reescritura",
                )

        # 3. Visual (Sub-orquestador maneja generacion + validacion de calidad)
        if not _fase_completada(proyecto_id, "visual"):
            validar_fase("visual")
            _fase(proyecto_id, "visual")
            _llamar("sub_orq_visual", proyecto_id)

        if not _fase_completada(proyecto_id, "audio"):
            validar_fase("audio")
            _fase(proyecto_id, "audio")
            _llamar("sub_orq_audio", proyecto_id)

        # 5. Cierre (Editor + SEO + Compliance + Publicador)
        if not _fase_completada(proyecto_id, "cierre"):
            validar_fase("cierre")
            _fase(proyecto_id, "cierre")
            _llamar("sub_orq_cierre", proyecto_id)

        state.actualizar(proyecto_id, fase_actual="completado", agente_actual=None)
        return state.leer(proyecto_id)

    except HTTPException:
        raise
    except HealthCheckError as exc:
        state.actualizar(
            proyecto_id,
            fase_actual="error",
            agente_actual=None,
            errores=[f"Pre-fase: {f}" for f in exc.fallos],
        )
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        state.actualizar(
            proyecto_id,
            fase_actual="error",
            agente_actual=None,
            errores=[str(exc)],
        )
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES["orquestador_central"])
