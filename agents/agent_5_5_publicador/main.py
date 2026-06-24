"""
Agente 5.5 - Publicador YouTube
Depto 5 (Cierre)

Sube el video final a YouTube con toda la metadata generada por el
pipeline (titulo, descripcion, tags, categoria, miniatura).

Requiere OAuth2 configurado (correr scripts/youtube_auth.py una vez).
Si las credenciales no estan, degrada con gracia y deja el video
listo para subir manualmente.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import (
    REGISTRO_AGENTES,
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN,
)
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "5.5_publicador"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Sube el video final a YouTube via OAuth2")
state = StateManager()

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
CATEGORY_MAP = {
    "education": "27",
    "entertainment": "24",
    "science & technology": "28",
    "howto & style": "26",
    "people & blogs": "22",
    "news & politics": "25",
    "gaming": "20",
    "film & animation": "1",
    "music": "10",
    "sports": "17",
}


def _get_youtube_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    credentials.refresh(Request())
    return build("youtube", "v3", credentials=credentials)


def _resolver_categoria(categoria_texto: str | None) -> str:
    if not categoria_texto:
        return "22"
    return CATEGORY_MAP.get(categoria_texto.lower(), "22")


def _subir_video(service, video_path: str, titulo: str, descripcion: str,
                 tags: list[str], categoria_id: str) -> str:
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": titulo[:100],
            "description": descripcion[:5000],
            "tags": tags[:500],
            "categoryId": categoria_id,
            "defaultLanguage": "es",
            "defaultAudioLanguage": "es",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response["id"]


def _subir_miniatura(service, video_id: str, miniatura_path: str) -> None:
    from googleapiclient.http import MediaFileUpload

    if not miniatura_path or not Path(miniatura_path).exists():
        return
    media = MediaFileUpload(miniatura_path, mimetype="image/png")
    service.thumbnails().set(videoId=video_id, media_body=media).execute()


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)

    if not estado.video_final_path:
        raise ValueError("No hay video final: corre primero el Agente 5.1 (Editor)")

    if not Path(estado.video_final_path).exists():
        raise ValueError(f"Archivo de video no encontrado: {estado.video_final_path}")

    if not all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN]):
        state.actualizar(request.proyecto_id, publicado=False)
        return {
            "publicado": False,
            "skipped_reason": (
                "Credenciales YouTube OAuth2 no configuradas. "
                "Corre scripts/youtube_auth.py para obtener el refresh token."
            ),
            "video_final_path": estado.video_final_path,
        }

    try:
        service = _get_youtube_service()
    except Exception as exc:
        state.actualizar(request.proyecto_id, publicado=False)
        return {
            "publicado": False,
            "skipped_reason": f"Error autenticando con YouTube: {exc}",
            "video_final_path": estado.video_final_path,
        }

    titulo = estado.estrategia.titulo_ganador or estado.proyecto_id
    descripcion = estado.metadata.descripcion or ""
    tags = estado.metadata.tags or []
    categoria_id = _resolver_categoria(estado.metadata.categoria)

    video_id = _subir_video(service, estado.video_final_path, titulo, descripcion, tags, categoria_id)

    miniatura_path = estado.estrategia.miniatura_path
    if miniatura_path:
        try:
            _subir_miniatura(service, video_id, miniatura_path)
        except Exception:
            pass

    state.actualizar(
        request.proyecto_id,
        publicado=True,
        youtube_video_id=video_id,
        publicado_en=datetime.utcnow().isoformat(),
    )

    return {
        "publicado": True,
        "youtube_video_id": video_id,
        "youtube_url": f"https://youtu.be/{video_id}",
        "privacy_status": "private",
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
