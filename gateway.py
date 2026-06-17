"""
API Gateway - YTCreator Studio v3
====================================

Punto de entrada externo UNICO. Redirige peticiones a los 16
microservicios internos sin modificarlos. Agrega endpoints de
webhook para n8n y descarga de video final.

Puertos internos: los 16 agentes en 8000-8502 (levantados por run_dev.py)
Puerto del gateway: 7860 (el que expone HF Spaces)
"""

import sys
import uuid
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import httpx
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from shared.config import REGISTRO_AGENTES, STORAGE_DIR, url_agente
from shared.state_manager import StateManager

app = FastAPI(title="YTCreator Studio v3 - Gateway", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

state = StateManager()

ORQUESTADOR_URL = url_agente("orquestador_central")
TIMEOUT_PIPELINE = 600


# ── Health ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"servicio": "gateway", "estado": "ok"}


# ── Proxy a orquestador central (proyectos + pipeline) ──────────────

@app.post("/proyectos")
def crear_proyecto(proyecto_id: str, canal: str):
    resp = httpx.post(
        f"{ORQUESTADOR_URL}/proyectos",
        params={"proyecto_id": proyecto_id, "canal": canal},
        timeout=30,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@app.get("/proyectos/{proyecto_id}")
def leer_proyecto(proyecto_id: str):
    resp = httpx.get(f"{ORQUESTADOR_URL}/proyectos/{proyecto_id}", timeout=30)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@app.get("/proyectos")
def listar_proyectos():
    resp = httpx.get(f"{ORQUESTADOR_URL}/proyectos", timeout=30)
    return resp.json()


@app.post("/pipeline/ejecutar")
def ejecutar_pipeline(proyecto_id: str, nicho: str):
    resp = httpx.post(
        f"{ORQUESTADOR_URL}/pipeline/ejecutar",
        params={"proyecto_id": proyecto_id, "nicho": nicho},
        timeout=TIMEOUT_PIPELINE,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


# ── Proxy a agentes individuales ────────────────────────────────────

@app.post("/agentes/{agente_id}/ejecutar")
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
    proyecto_id: str | None = None
    callback_url: str | None = None
    parametros: dict = Field(default_factory=dict)


class KaggleCallbackRequest(BaseModel):
    proyecto_id: str
    status: str
    error: str | None = None


def _run_pipeline_async(proyecto_id: str, nicho: str, callback_url: str | None):
    try:
        httpx.post(
            f"{ORQUESTADOR_URL}/pipeline/ejecutar",
            params={"proyecto_id": proyecto_id, "nicho": nicho},
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


@app.post("/pipeline/webhook")
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
        request.callback_url,
    )

    return {
        "proyecto_id": proyecto_id,
        "estado": "iniciado",
        "mensaje": "Pipeline lanzado en background",
    }


@app.post("/pipeline/kaggle-callback")
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


# ── Estado del pipeline ─────────────────────────────────────────────

@app.get("/pipeline/estado/{proyecto_id}")
def pipeline_estado(proyecto_id: str):
    try:
        estado = state.leer(proyecto_id)
        return {
            "proyecto_id": proyecto_id,
            "fase_actual": estado.fase_actual,
            "guion_aprobado": estado.guion.aprobado,
            "visual_listo": estado.visual.prompts_generados,
            "audio_listo": estado.audio.voz_path is not None,
            "video_final": estado.video_final_path,
            "publicado": estado.publicado,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Proyecto '{proyecto_id}' no encontrado")


# ── Descarga de video final ─────────────────────────────────────────

@app.get("/download/{proyecto_id}/final")
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
    uvicorn.run(app, host="0.0.0.0", port=7860)
