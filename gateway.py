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
from shared.visual_styles import (
    CATEGORIAS,
    aplicar_estilo,
    listar_categorias,
    listar_estilos,
    obtener_estilo,
)
from shared.youtube_client import obtener_quota_hoy

log = get_logger("gateway")

app = FastAPI(title="YTCreator Studio v3 - Gateway", version="3.0.0")

from shared import event_store
event_store.registrar("system_startup", "success", source="gateway", data={"version": "3.0.0"})

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
    from shared import scheduler

    if scheduler.esta_pausado():
        pausa = scheduler.obtener_pausa()
        event_store.registrar(
            "pipeline_blocked", "warning",
            source="gateway",
            data={"razon": "automatizacion pausada", "nicho": request.nicho},
        )
        raise HTTPException(
            status_code=409,
            detail=f"Automatizacion pausada{': ' + pausa['razon'] if pausa.get('razon') else ''}. Reanuda desde el panel para lanzar pipelines.",
        )

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


class IdentidadVisualRequest(BaseModel):
    estilo_slug: str
    personaje_principal: str | None = None
    personaje_nombre: str | None = None
    elementos_recurrentes: list[str] = Field(default_factory=list)
    paleta_colores: str | None = None
    fondo_base: str | None = None
    iluminacion: str | None = None
    prompt_template: str | None = None
    negative_prompt: str | None = None


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


# ── Estilos visuales e Identidad de Canal ────────────────────────────

@app.get("/estilos")
def get_estilos(categoria: str | None = None):
    return {
        "categorias": listar_categorias(),
        "estilos": listar_estilos(categoria),
    }


@app.get("/estilos/{slug}")
def get_estilo(slug: str):
    estilo = obtener_estilo(slug)
    if not estilo:
        raise HTTPException(status_code=404, detail=f"Estilo '{slug}' no encontrado")
    return estilo


@app.get("/canales/{canal_id}/identidad-visual", dependencies=[Depends(verificar_api_key)])
def get_identidad_visual(canal_id: str):
    try:
        estado = channel_mgr.leer(canal_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Canal '{canal_id}' no encontrado")
    return estado.identidad_visual.model_dump()


@app.post("/canales/{canal_id}/identidad-visual", dependencies=[Depends(verificar_api_key)])
def set_identidad_visual(canal_id: str, request: IdentidadVisualRequest):
    try:
        channel_mgr.leer(canal_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Canal '{canal_id}' no encontrado")

    if request.estilo_slug == "custom":
        if not request.prompt_template or "{prompt}" not in request.prompt_template:
            raise HTTPException(
                status_code=422,
                detail="Para estilo 'custom', prompt_template es obligatorio y debe contener {prompt}",
            )
        prompt_tpl = request.prompt_template
        neg_prompt = request.negative_prompt or ""
    else:
        estilo = obtener_estilo(request.estilo_slug)
        if not estilo:
            raise HTTPException(
                status_code=422,
                detail=f"Estilo '{request.estilo_slug}' no existe en el catalogo",
            )
        prompt_tpl = estilo["prompt_template"]
        neg_prompt = estilo["negative_prompt"]

    identidad_data = {
        "configurado": True,
        "estilo_slug": request.estilo_slug,
        "prompt_template": prompt_tpl,
        "negative_prompt": neg_prompt,
        "personaje_principal": request.personaje_principal,
        "personaje_nombre": request.personaje_nombre,
        "elementos_recurrentes": request.elementos_recurrentes,
        "paleta_colores": request.paleta_colores,
        "fondo_base": request.fondo_base,
        "iluminacion": request.iluminacion,
    }

    channel_mgr.actualizar(canal_id, identidad_visual=identidad_data)
    return channel_mgr.leer(canal_id).identidad_visual.model_dump()


# ── Scheduling & Health de servicios ───────────────────────────────

@app.get("/scheduling/health_servicios", dependencies=[Depends(verificar_api_key)])
def health_servicios():
    resp = httpx.get(f"{ORQUESTADOR_URL}/scheduling/health_servicios", timeout=30)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@app.post("/scheduling/puede_generar", dependencies=[Depends(verificar_api_key)])
def puede_generar(canal_id: str | None = None, frecuencia: str | None = None):
    params = {}
    if canal_id:
        params["canal_id"] = canal_id
    if frecuencia:
        params["frecuencia"] = frecuencia
    resp = httpx.post(f"{ORQUESTADOR_URL}/scheduling/puede_generar", params=params, timeout=30)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


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


# ── Cola de publicación ────────────────────────────────────────────

@app.get("/pipeline/cola", dependencies=[Depends(verificar_api_key)])
def pipeline_cola():
    from shared.config import BUFFER_MAX_VIDEOS

    proyectos_ids = state.listar_proyectos()
    en_proceso = []
    listos = []
    publicados_list = []
    con_error = []

    for pid in proyectos_ids:
        try:
            est = state.leer(pid)
        except Exception:
            continue

        historial_resumen = [
            {
                "agente_id": r.agente_id,
                "estado": r.estado.value if hasattr(r.estado, "value") else r.estado,
                "inicio": r.inicio.isoformat() if r.inicio else None,
                "fin": r.fin.isoformat() if r.fin else None,
                "duracion_seg": r.duracion_seg,
                "intentos": r.intentos,
                "error": r.error,
            }
            for r in est.historial_agentes
        ]

        item = {
            "proyecto_id": pid,
            "fase_actual": est.fase_actual,
            "titulo": est.estrategia.titulo_ganador or pid,
            "canal": est.canal,
            "creado_en": est.creado_en.isoformat() if est.creado_en else None,
            "actualizado_en": est.actualizado_en.isoformat() if est.actualizado_en else None,
            "publicado": est.publicado,
            "youtube_video_id": est.youtube_video_id,
            "publicado_en": est.publicado_en.isoformat() if est.publicado_en else None,
            "video_final_path": est.video_final_path,
            "agente_actual": est.agente_actual,
            "errores": est.errores,
            "nicho": est.estrategia.nicho,
            "progreso_pct": min(round(len(est.historial_agentes) / TOTAL_AGENTES_PIPELINE * 100), 100),
            "historial": historial_resumen,
        }

        if est.publicado:
            publicados_list.append(item)
        elif est.fase_actual == "completado":
            listos.append(item)
        elif est.fase_actual == "error":
            con_error.append(item)
        elif est.fase_actual in ("estrategia", "guion", "visual", "audio", "cierre"):
            en_proceso.append(item)

    publicados_list.sort(key=lambda x: x.get("publicado_en") or "", reverse=True)
    listos.sort(key=lambda x: x.get("actualizado_en") or "", reverse=True)
    en_proceso.sort(key=lambda x: x.get("creado_en") or "", reverse=True)
    con_error.sort(key=lambda x: x.get("actualizado_en") or "", reverse=True)

    return {
        "buffer": {"actual": len(listos), "max": BUFFER_MAX_VIDEOS},
        "en_proceso": en_proceso,
        "listos_para_publicar": listos,
        "publicados": publicados_list[:10],
        "con_error": con_error,
        "total_proyectos": len(proyectos_ids),
    }


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


# ── Eventos de automatización ──────────────────────────────────────

@app.get("/eventos", dependencies=[Depends(verificar_api_key)])
def listar_eventos(
    limit: int = 100,
    event_type: str | None = None,
    status: str | None = None,
    proyecto_id: str | None = None,
    source: str | None = None,
    desde: str | None = None,
):
    from shared import event_store
    return {
        "eventos": event_store.consultar(
            limit=limit,
            event_type=event_type,
            status=status,
            proyecto_id=proyecto_id,
            source=source,
            desde=desde,
        ),
    }


@app.get("/eventos/stats", dependencies=[Depends(verificar_api_key)])
def eventos_stats():
    from shared import event_store
    return event_store.contar()


@app.post("/eventos/purgar", dependencies=[Depends(verificar_api_key)])
def purgar_eventos(dias: int = 90):
    from shared import event_store
    eliminados = event_store.purgar(dias=dias)
    return {"eliminados": eliminados, "dias_cutoff": dias}


# ── Scheduler (tareas programadas) ────────────────────────────────

@app.get("/scheduler", dependencies=[Depends(verificar_api_key)])
def scheduler_resumen():
    from shared import scheduler
    return scheduler.resumen()


@app.get("/scheduler/tareas", dependencies=[Depends(verificar_api_key)])
def scheduler_tareas():
    from shared import scheduler
    return {"tareas": scheduler.listar_tareas()}


@app.post("/scheduler/tareas/{task_id}/toggle", dependencies=[Depends(verificar_api_key)])
def scheduler_toggle(task_id: str, habilitado: bool):
    from shared import scheduler
    result = scheduler.toggle_tarea(task_id, habilitado)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Tarea '{task_id}' no encontrada")
    event_store.registrar(
        "scheduler_toggle", "success",
        source="gateway",
        data={"task_id": task_id, "habilitado": habilitado},
    )
    return result


@app.get("/scheduler/pausa", dependencies=[Depends(verificar_api_key)])
def scheduler_pausa_estado():
    from shared import scheduler
    return scheduler.obtener_pausa()


@app.post("/scheduler/pausar", dependencies=[Depends(verificar_api_key)])
def scheduler_pausar(razon: str | None = None):
    from shared import scheduler
    result = scheduler.pausar(razon=razon)
    event_store.registrar(
        "automation_paused", "warning",
        source="gateway",
        data={"razon": razon},
    )
    log.warning("AUTOMATIZACION PAUSADA — razon: %s", razon or "sin razon")
    return result


@app.post("/scheduler/reanudar", dependencies=[Depends(verificar_api_key)])
def scheduler_reanudar():
    from shared import scheduler
    result = scheduler.reanudar()
    event_store.registrar(
        "automation_resumed", "success",
        source="gateway",
    )
    log.info("AUTOMATIZACION REANUDADA")
    return result


# ── Keyword Performance Tracking ──────────────────────────────────

@app.get("/keywords/top", dependencies=[Depends(verificar_api_key)])
def keywords_top(limit: int = 30, ordenar_por: str = "vistas_promedio", min_usos: int = 1):
    from shared import keyword_tracker
    return {"keywords": keyword_tracker.top_keywords(limit=limit, ordenar_por=ordenar_por, min_usos=min_usos)}


@app.get("/keywords/{keyword}/historial", dependencies=[Depends(verificar_api_key)])
def keyword_historial(keyword: str, limit: int = 20):
    from shared import keyword_tracker
    return {"keyword": keyword, "historial": keyword_tracker.historial_keyword(keyword, limit=limit)}


@app.get("/keywords/stats", dependencies=[Depends(verificar_api_key)])
def keywords_stats():
    from shared import keyword_tracker
    return keyword_tracker.stats()


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7861)
