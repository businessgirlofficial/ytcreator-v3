"""
Agente 0.1 - Escaner de Canal
Depto 0 (Inteligencia de Canal)

Conecta con YouTube Data API v3 para extraer datos crudos de un canal:
  - Metadata del canal (nombre, suscriptores, descripcion, etc.)
  - Lista de videos recientes (ultimos 50-100)
  - Metricas por video (vistas, likes, comentarios, duracion, tags)

Usa playlistItems.list (1 unit/pagina) en vez de search.list (100 units)
para mantenerse dentro del tier gratuito de quota.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.channel_manager import ChannelManager
from shared.config import REGISTRO_AGENTES
from shared.schemas import AgenteRequest, AgenteResponse, VideoRendimiento
from shared.youtube_client import (
    obtener_canal,
    obtener_metricas_videos,
    obtener_videos_recientes,
)

AGENTE_ID = "0.1_escaner_canal"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Escanea un canal de YouTube via Data API v3")
channels = ChannelManager()

MAX_VIDEOS_ESCANEO = 50


def logica(request: AgenteRequest) -> dict:
    canal_input = request.parametros.get("canal_input", "")
    if not canal_input:
        raise ValueError("Falta el parametro 'canal_input' (URL, @handle o channel ID)")

    canal_data = obtener_canal(canal_input)
    canal_id = canal_data["id"]

    try:
        channels.leer(canal_id)
    except FileNotFoundError:
        channels.crear(canal_id, canal_data["nombre"])

    channels.actualizar(
        canal_id,
        nombre=canal_data["nombre"],
        descripcion=canal_data.get("descripcion"),
        url=f"https://www.youtube.com/channel/{canal_id}",
        suscriptores=canal_data.get("suscriptores"),
        video_count=canal_data.get("video_count"),
        vistas_totales=canal_data.get("vistas_totales"),
        uploads_playlist_id=canal_data.get("uploads_playlist_id"),
        miniatura_url=canal_data.get("miniatura_url"),
        banner_url=canal_data.get("banner_url"),
        creado_youtube=canal_data.get("creado_youtube"),
    )

    uploads_playlist = canal_data.get("uploads_playlist_id")
    videos_data = []
    if uploads_playlist:
        video_ids = obtener_videos_recientes(uploads_playlist, max_videos=MAX_VIDEOS_ESCANEO)
        if video_ids:
            videos_data = obtener_metricas_videos(video_ids)

    videos_rendimiento = [
        VideoRendimiento(
            video_id=v["video_id"],
            titulo=v["titulo"],
            publicado_en=v.get("publicado_en"),
            vistas=v.get("vistas", 0),
            likes=v.get("likes", 0),
            comentarios=v.get("comentarios", 0),
            duracion_seg=v.get("duracion_seg"),
            miniatura_url=v.get("miniatura_url"),
            tags=v.get("tags", []),
            categoria_id=v.get("categoria_id"),
        )
        for v in videos_data
    ]

    top_videos = sorted(videos_rendimiento, key=lambda v: v.vistas, reverse=True)[:10]

    channels.actualizar(
        canal_id,
        videos_recientes=[v.model_dump() for v in videos_rendimiento],
        top_videos=[v.model_dump() for v in top_videos],
        escaneado_en=datetime.utcnow().isoformat(),
    )

    return {
        "canal_id": canal_id,
        "nombre": canal_data["nombre"],
        "suscriptores": canal_data.get("suscriptores"),
        "videos_escaneados": len(videos_rendimiento),
        "top_video": top_videos[0].titulo if top_videos else None,
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
