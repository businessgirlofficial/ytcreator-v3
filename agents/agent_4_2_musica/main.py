"""
Agente 4.2 - Productor musical
Depto 4 (Audio)

Genera o busca musica de fondo para el video.

FUENTE PRINCIPAL: MusicGen de Meta via Hugging Face Inference API.
  - Gratuito (tier free con rate limits)
  - Genera musica a medida del mood del video
  - Pistas de ~30 segundos, el Editor (5.1) las loopea automaticamente

FALLBACK: Pixabay Music API (endpoint no documentado oficialmente).
  - Si MusicGen falla (rate limit, modelo cargando, HF caido), se
    intenta buscar en Pixabay por keyword del mood.
  - Si Pixabay tambien falla, el agente lanza error y el
    sub-orquestador reintenta.
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import httpx
import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import HF_API_TOKEN, PIXABAY_API_KEY, REGISTRO_AGENTES, STORAGE_DIR
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "4.2_musica"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Genera o busca musica de fondo segun el mood")
state = StateManager()

HF_MUSICGEN_URL = "https://api-inference.huggingface.co/models/facebook/musicgen-small"
HF_MAX_ESPERA_CARGA = 120
HF_POLL_INTERVAL = 10


def _construir_prompt_musicgen(mood: str | None) -> str:
    base = "instrumental background music for a YouTube video"
    if mood:
        return f"{base}, mood: {mood}, no vocals, loopable, cinematic"
    return f"{base}, neutral calm ambient, no vocals, loopable"


def _generar_musicgen(mood: str | None, proyecto_id: str) -> str:
    if not HF_API_TOKEN:
        raise RuntimeError(
            "HF_API_TOKEN no esta configurada. Generala gratis en "
            "huggingface.co/settings/tokens"
        )

    prompt = _construir_prompt_musicgen(mood)
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}

    esperado = 0
    while esperado < HF_MAX_ESPERA_CARGA:
        resp = httpx.post(
            HF_MUSICGEN_URL,
            headers=headers,
            json={"inputs": prompt},
            timeout=180,
        )

        if resp.status_code == 503:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            wait = min(body.get("estimated_time", HF_POLL_INTERVAL), 30)
            time.sleep(wait)
            esperado += wait
            continue

        if resp.status_code == 429:
            raise RuntimeError("MusicGen: rate limit de HF alcanzado")

        resp.raise_for_status()
        break
    else:
        raise RuntimeError(
            f"MusicGen: el modelo no termino de cargar tras {HF_MAX_ESPERA_CARGA}s"
        )

    content_type = resp.headers.get("content-type", "")
    if "flac" in content_type:
        extension = ".flac"
    elif "wav" in content_type:
        extension = ".wav"
    elif "mpeg" in content_type or "mp3" in content_type:
        extension = ".mp3"
    else:
        extension = ".flac"

    musica_dir = Path(STORAGE_DIR) / "proyectos" / proyecto_id / "musica"
    musica_dir.mkdir(parents=True, exist_ok=True)
    destino = musica_dir / f"background{extension}"
    destino.write_bytes(resp.content)

    return str(destino)


def _buscar_pixabay(mood: str, proyecto_id: str) -> str:
    if not PIXABAY_API_KEY:
        raise RuntimeError("PIXABAY_API_KEY no esta configurada en tu .env")

    resp = httpx.get(
        "https://pixabay.com/api/music/",
        params={"key": PIXABAY_API_KEY, "q": mood, "per_page": 5},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    if not data.get("hits"):
        raise RuntimeError(f"No se encontro musica para mood '{mood}' en Pixabay")

    hit = data["hits"][0]
    audio_url = hit.get("audio") or hit.get("previewURL") or hit.get("url", "")
    if not audio_url:
        raise RuntimeError("Pixabay devolvio resultado sin URL de audio")

    musica_dir = Path(STORAGE_DIR) / "proyectos" / proyecto_id / "musica"
    musica_dir.mkdir(parents=True, exist_ok=True)
    destino = musica_dir / "background.mp3"

    audio_resp = httpx.get(audio_url, timeout=60)
    audio_resp.raise_for_status()
    destino.write_bytes(audio_resp.content)

    return str(destino)


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    mood = estado.estrategia.mood
    fuente = "musicgen"
    error_musicgen = None

    try:
        musica_path = _generar_musicgen(mood, request.proyecto_id)
    except Exception as exc:
        error_musicgen = str(exc)
        fuente = "pixabay"
        musica_path = _buscar_pixabay(mood or "epic cinematic", request.proyecto_id)

    state.actualizar(
        request.proyecto_id,
        audio={"musica_path": musica_path, "musica_fuente": fuente, "musica_volumen_db": -20.0},
    )
    resultado = {"mood": mood, "musica_fuente": fuente, "musica_path": musica_path}
    if error_musicgen:
        resultado["musicgen_fallback_reason"] = error_musicgen
    return resultado


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
