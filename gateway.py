"""
API Gateway - YTCreator Studio v3
====================================

Punto de entrada externo UNICO. Redirige peticiones a los 16
microservicios internos sin modificarlos. Agrega endpoints de
webhook para n8n y descarga de video final.

Puertos internos: los 16 agentes en 8000-8502 (levantados por run_dev.py)
Puerto del gateway: 7861 (nginx en 7860 rutea /api/* aqui)
"""

import sys
import time
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import httpx
import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.responses import Response

from shared.channel_manager import ChannelManager
from shared.config import REGISTRO_AGENTES, STORAGE_DIR, YTCREATOR_API_KEY, url_agente
from shared.logger import get_logger
from shared.state_manager import StateManager
from shared.youtube_client import obtener_quota_hoy

log = get_logger("gateway")

app = FastAPI(title="YTCreator Studio v3 - Gateway", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    inicio = time.time()
    response: Response = await call_next(request)
    duracion = round(time.time() - inicio, 2)
    log.info("%s %s | status=%d | duracion=%.2fs", request.method, request.url.path, response.status_code, duracion)
    return response

state = StateManager()
channel_mgr = ChannelManager()

ORQUESTADOR_URL = url_agente("orquestador_central")
TIMEOUT_PIPELINE = 600


# ── Auth ───────────────────────────────────────────────────────────

RUTAS_PUBLICAS = {"/health", "/docs", "/openapi.json"}


async def verificar_api_key(request: Request):
    if request.url.path in RUTAS_PUBLICAS:
        return
    if not YTCREATOR_API_KEY:
        return
    api_key = request.headers.get("X-API-Key")
    if api_key != YTCREATOR_API_KEY:
        raise HTTPException(status_code=401, detail="API key invalida o no proporcionada")


# ── Health ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"servicio": "gateway", "estado": "ok"}


# ── Proxy a orquestador central (proyectos + pipeline) ──────────────

@app.post("/proyectos", dependencies=[Depends(verificar_api_key)])
def crear_proyecto(proyecto_id: str, canal: str):
    resp = httpx.post(
        f"{ORQUESTADOR_URL}/proyectos",
        params={"proyecto_id": proyecto_id, "canal": canal},
        timeout=30,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@app.get("/proyectos/{proyecto_id}", dependencies=[Depends(verificar_api_key)])
def leer_proyecto(proyecto_id: str):
    resp = httpx.get(f"{ORQUESTADOR_URL}/proyectos/{proyecto_id}", timeout=30)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@app.get("/proyectos", dependencies=[Depends(verificar_api_key)])
def listar_proyectos():
    resp = httpx.get(f"{ORQUESTADOR_URL}/proyectos", timeout=30)
    return resp.json()


@app.post("/pipeline/ejecutar", dependencies=[Depends(verificar_api_key)])
def ejecutar_pipeline(proyecto_id: str, nicho: str, canal: str = "mi_canal", canal_id: str | None = None):
    params = {"proyecto_id": proyecto_id, "nicho": nicho, "canal": canal}
    if canal_id:
        params["canal_id"] = canal_id
    resp = httpx.post(
        f"{ORQUESTADOR_URL}/pipeline/ejecutar",
        params=params,
        timeout=TIMEOUT_PIPELINE,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


# ── Proxy a agentes individuales ────────────────────────────────────

@app.post("/agentes/{agente_id}/ejecutar", dependencies=[Depends(verificar_api_key)])
def ejecutar_agente(agente_id: str, request: dict):
    if agente_id not in REGISTRO_AGENTES:
        raise HTTPException(status_code=404, detail=f"Agente '{agente_id}' no existe")
    resp = httpx.post(
        f"{url_agente(agente_id)}/ejecutar",
        json=request,
        timeout=300,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


# ── Webhook para n8n ────────────────────────────────────────────────

class WebhookRequest(BaseModel):
    nicho: str
    canal: str = "MiCanal"
    canal_id: str | None = None
    proyecto_id: str | None = None
    callback_url: str | None = None
    parametros: dict = Field(default_factory=dict)


class KaggleCallbackRequest(BaseModel):
    proyecto_id: str
    status: str
    error: str | None = None


def _run_pipeline_async(proyecto_id: str, nicho: str, canal: str, callback_url: str | None, canal_id: str | None = None):
    try:
        params = {"proyecto_id": proyecto_id, "nicho": nicho, "canal": canal}
        if canal_id:
            params["canal_id"] = canal_id
        httpx.post(
            f"{ORQUESTADOR_URL}/pipeline/ejecutar",
            params=params,
            timeout=TIMEOUT_PIPELINE,
        )
        if callback_url:
            estado = state.leer(proyecto_id)
            httpx.post(
                callback_url,
                json={
                    "proyecto_id": proyecto_id,
                    "estado": "completado",
                    "video_final_path": estado.video_final_path,
                },
                timeout=30,
            )
    except Exception as exc:
        if callback_url:
            httpx.post(
                callback_url,
                json={
                    "proyecto_id": proyecto_id,
                    "estado": "error",
                    "error": str(exc),
                },
                timeout=30,
            )


@app.post("/pipeline/webhook", dependencies=[Depends(verificar_api_key)])
def webhook_trigger(request: WebhookRequest, background_tasks: BackgroundTasks):
    proyecto_id = request.proyecto_id or f"proy_{uuid.uuid4().hex[:8]}"

    try:
        state.crear(proyecto_id, request.canal)
    except FileExistsError:
        pass

    background_tasks.add_task(
        _run_pipeline_async,
        proyecto_id,
        request.nicho,
        request.canal,
        request.callback_url,
        request.canal_id,
    )

    return {
        "proyecto_id": proyecto_id,
        "estado": "iniciado",
        "mensaje": "Pipeline lanzado en background",
    }


@app.post("/pipeline/kaggle-callback", dependencies=[Depends(verificar_api_key)])
def kaggle_callback(request: KaggleCallbackRequest):
    try:
        estado = state.leer(request.proyecto_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Proyecto '{request.proyecto_id}' no encontrado")

    if request.status == "complete":
        state.actualizar(request.proyecto_id, visual={"generacion_completada": True})
        return {"estado": "recibido", "proyecto_id": request.proyecto_id}
    else:
        state.actualizar(
            request.proyecto_id,
            fase_actual="error",
            errores=[f"Kaggle fallo: {request.error or 'error desconocido'}"],
        )
        raise HTTPException(status_code=422, detail=f"Kaggle reporto error: {request.error}")


# ── Channel Intelligence ───────────────────────────────────────────


class ConectarCanalRequest(BaseModel):
    canal_input: str


class AgregarCompetidorRequest(BaseModel):
    competidor_input: str


@app.post("/canales/conectar", dependencies=[Depends(verificar_api_key)])
def conectar_canal(request: ConectarCanalRequest, background_tasks: BackgroundTasks):
    resp = httpx.post(
        f"{url_agente('sub_orq_inteligencia')}/ejecutar",
        json={
            "proyecto_id": "canal_setup",
            "parametros": {
                "canal_input": request.canal_input,
                "modo": "completo",
            },
        },
        timeout=300,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    canal_id = data.get("output", {}).get("canal_id")
    if canal_id:
        try:
            return channel_mgr.leer(canal_id).model_dump()
        except FileNotFoundError:
            return data
    return data


@app.get("/canales", dependencies=[Depends(verificar_api_key)])
def listar_canales():
    return {"canales": channel_mgr.listar_canales()}


@app.get("/canales/{canal_id}", dependencies=[Depends(verificar_api_key)])
def leer_canal(canal_id: str):
    try:
        return channel_mgr.leer(canal_id).model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Canal '{canal_id}' no encontrado")


@app.post("/canales/{canal_id}/refrescar", dependencies=[Depends(verificar_api_key)])
def refrescar_canal(canal_id: str):
    resp = httpx.post(
        f"{url_agente('sub_orq_inteligencia')}/ejecutar",
        json={
            "proyecto_id": "canal_refresh",
            "parametros": {
                "canal_id": canal_id,
                "canal_input": canal_id,
                "modo": "completo",
            },
        },
        timeout=300,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    try:
        return channel_mgr.leer(canal_id).model_dump()
    except FileNotFoundError:
        return resp.json()


@app.delete("/canales/{canal_id}", dependencies=[Depends(verificar_api_key)])
def eliminar_canal(canal_id: str):
    try:
        channel_mgr.eliminar(canal_id)
        return {"eliminado": True, "canal_id": canal_id}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Canal '{canal_id}' no encontrado")


@app.post("/canales/{canal_id}/competidores", dependencies=[Depends(verificar_api_key)])
def agregar_competidor(canal_id: str, request: AgregarCompetidorRequest):
    try:
        estado = channel_mgr.leer(canal_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Canal '{canal_id}' no encontrado")

    resp = httpx.post(
        f"{url_agente('0.1_escaner_canal')}/ejecutar",
        json={
            "proyecto_id": "comp_scan",
            "parametros": {"canal_input": request.competidor_input},
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    comp_data = resp.json().get("output", {})
    comp_id = comp_data.get("canal_id", "")
    if not comp_id:
        raise HTTPException(status_code=422, detail="No se pudo resolver el canal competidor")

    ya_existe = any(c.channel_id == comp_id for c in estado.competidores)
    if ya_existe:
        return {"mensaje": "Competidor ya agregado", "channel_id": comp_id}

    from shared.schemas import CompetidorInfo
    nuevo_comp = CompetidorInfo(
        channel_id=comp_id,
        nombre=comp_data.get("nombre", ""),
        suscriptores=comp_data.get("suscriptores"),
    )
    competidores = estado.competidores + [nuevo_comp]
    channel_mgr.actualizar(canal_id, competidores=[c.model_dump() for c in competidores])
    return {"agregado": True, "channel_id": comp_id, "nombre": comp_data.get("nombre")}


@app.delete("/canales/{canal_id}/competidores/{comp_id}", dependencies=[Depends(verificar_api_key)])
def eliminar_competidor(canal_id: str, comp_id: str):
    try:
        estado = channel_mgr.leer(canal_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Canal '{canal_id}' no encontrado")

    competidores = [c for c in estado.competidores if c.channel_id != comp_id]
    if len(competidores) == len(estado.competidores):
        raise HTTPException(status_code=404, detail=f"Competidor '{comp_id}' no encontrado")

    channel_mgr.actualizar(canal_id, competidores=[c.model_dump() for c in competidores])
    return {"eliminado": True, "comp_id": comp_id}


@app.get("/canales/{canal_id}/ideas", dependencies=[Depends(verificar_api_key)])
def obtener_ideas(canal_id: str):
    try:
        estado = channel_mgr.leer(canal_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Canal '{canal_id}' no encontrado")
    return {"canal_id": canal_id, "ideas": estado.ideas_sugeridas}


@app.post("/canales/{canal_id}/ideas/refrescar", dependencies=[Depends(verificar_api_key)])
def refrescar_ideas(canal_id: str):
    resp = httpx.post(
        f"{url_agente('0.4_asesor_estrategico')}/ejecutar",
        json={
            "proyecto_id": "ideas_refresh",
            "parametros": {"canal_id": canal_id},
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    try:
        estado = channel_mgr.leer(canal_id)
        return {"canal_id": canal_id, "ideas": estado.ideas_sugeridas}
    except FileNotFoundError:
        return resp.json()


@app.get("/quota/hoy", dependencies=[Depends(verificar_api_key)])
def quota_hoy():
    return obtener_quota_hoy()


# ── Estado del pipeline ─────────────────────────────────────────────

TOTAL_AGENTES_PIPELINE = 16


@app.get("/pipeline/estado/{proyecto_id}", dependencies=[Depends(verificar_api_key)])
def pipeline_estado(proyecto_id: str):
    try:
        estado = state.leer(proyecto_id)

        completados = len(estado.historial_agentes)
        progreso_pct = min(round(completados / TOTAL_AGENTES_PIPELINE * 100), 100)

        historial_resumen = [
            {
                "agente_id": r.agente_id,
                "estado": r.estado.value if hasattr(r.estado, "value") else r.estado,
                "duracion_seg": r.duracion_seg,
                "intentos": r.intentos,
                "error": r.error,
            }
            for r in estado.historial_agentes
        ]

        return {
            "proyecto_id": proyecto_id,
            "fase_actual": estado.fase_actual,
            "agente_actual": estado.agente_actual,
            "progreso_pct": progreso_pct,
            "agentes_completados": completados,
            "agentes_totales": TOTAL_AGENTES_PIPELINE,
            "fases": {
                "estrategia": bool(estado.estrategia.titulo_ganador),
                "guion": estado.guion.aprobado,
                "visual": estado.visual.prompts_generados,
                "audio": estado.audio.voz_path is not None,
                "video_final": estado.video_final_path is not None,
                "publicado": estado.publicado,
            },
            "video_final_path": estado.video_final_path,
            "youtube_video_id": estado.youtube_video_id,
            "errores": estado.errores,
            "historial": historial_resumen,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Proyecto '{proyecto_id}' no encontrado")


# ── Descarga de video final ─────────────────────────────────────────

@app.get("/download/{proyecto_id}/final", dependencies=[Depends(verificar_api_key)])
def download_final(proyecto_id: str):
    try:
        estado = state.leer(proyecto_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Proyecto '{proyecto_id}' no encontrado")

    if not estado.video_final_path:
        raise HTTPException(status_code=404, detail="No hay video final generado todavia")

    video_path = Path(estado.video_final_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Archivo de video no encontrado en disco")

    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        filename=f"{proyecto_id}_final.mp4",
    )


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7861)
