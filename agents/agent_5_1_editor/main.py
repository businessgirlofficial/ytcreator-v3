"""
Agente 5.1 - Editor tecnico
Depto 5 (Cierre)

FASE 5 - IMPLEMENTACION REAL
================================
Ensambla el video final con MoviePy: por cada escena, un clip de video
real (con loop si es mas corto que su duracion asignada, o recorte si
es mas largo) o una imagen con zoom cinematografico (efecto Ken Burns);
las concatena en orden; superpone voz + musica de fondo; quema los
subtitulos desde el .srt; exporta el .mp4 final.

IMPORTANTE -- verificado de verdad, no adivinado: instale MoviePy 2.x
en este entorno e inspeccione su API real (cambio MUCHO entre v1 y
v2: ya no existe `moviepy.editor`, los metodos pasaron de
`set_duration`/`resize`/`subclip` a `with_duration`/`resized`/
`subclipped`, los efectos viven en `vfx.*` y se aplican con
`with_effects([...])`). Probe el pipeline completo end-to-end de
verdad en este sandbox (no con mocks): imagen con zoom + subtitulos
quemados + audio compuesto + exportacion a .mp4 real, y tambien el
caso de un clip de video mas corto que su duracion asignada (loop).

DOS COSAS QUE DEBES CONFIRMAR/AJUSTAR:
  1. SUBTITULOS_FONT_PATH en tu .env: MoviePy 2.x exige una ruta real
     a un archivo .ttf/.otf para quemar texto -- no tiene un default
     universal entre sistemas operativos. En Windows, algo como
     C:\\Windows\\Fonts\\arialbd.ttf deberia funcionar.
  2. La forma en que emparejo cada escena con su archivo de imagen o
     clip: busco un numero en el nombre del archivo (ej. "escena_3.png").
     Si tu notebook v7 nombra los archivos de otra forma, esto no
     los va a encontrar -- avisame el patron real y lo ajusto.
"""

import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import moviepy
import uvicorn
from fastapi import FastAPI
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.tools.subtitles import SubtitlesClip

from shared.base_agent import crear_agente_app, envolver_logica, shutdown_requested
from shared.config import FPS_VIDEO, REGISTRO_AGENTES, RESOLUCION_VIDEO, STORAGE_DIR, SUBTITULOS_FONT_PATH
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "5.1_editor"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Ensambla el video final con MoviePy")
state = StateManager()

SALIDA_DIR = Path(STORAGE_DIR) / "video"

# Patron para extraer el numero de escena de un nombre de archivo, ej.
# "escena_3.png" -> 3, "escena-12.mp4" -> 12. AJUSTAR si tu notebook
# nombra los archivos distinto.
PATRON_NUMERO_ESCENA = re.compile(r"escena[_-]?(\d+)", re.IGNORECASE)

ZOOM_INICIAL = 1.0
ZOOM_FINAL = 1.08  # 8% de zoom total a lo largo de la escena -- sutil, no mareador


def _parsear_resolucion(texto: str) -> tuple[int, int]:
    ancho, alto = texto.lower().split("x")
    return int(ancho), int(alto)


def _indexar_por_numero(rutas: list[str]) -> dict[int, str]:
    indice = {}
    for ruta in rutas:
        coincidencia = PATRON_NUMERO_ESCENA.search(Path(ruta).stem)
        if coincidencia:
            indice[int(coincidencia.group(1))] = ruta
    return indice


from shared.video_utils import calcular_duraciones_por_palabras


def _construir_clip_escena(escena: dict, duracion: float, imagenes: dict, clips: dict, resolucion: tuple) -> "moviepy.VideoClip":
    numero = escena["numero"]

    if escena.get("usa_video_ia") and numero in clips:
        clip = VideoFileClip(clips[numero]).resized(resolucion)
        if clip.duration < duracion:
            clip = clip.with_effects([moviepy.vfx.Loop(duration=duracion)])
        else:
            clip = clip.subclipped(0, duracion)
        return clip.with_duration(duracion)

    if numero in imagenes:
        base = ImageClip(imagenes[numero]).with_duration(duracion).resized(resolucion)
        factor = ZOOM_FINAL - ZOOM_INICIAL
        animado = base.with_effects([moviepy.vfx.Resize(lambda t: ZOOM_INICIAL + factor * (t / max(duracion, 0.001)))])
        animado = animado.with_position("center")
        return CompositeVideoClip([animado], size=resolucion).with_duration(duracion)

    raise ValueError(
        f"La escena {numero} no tiene clip de video ni imagen asignada. "
        "Revisa que el Agente 3.2 (Generador visual) haya corrido y que el "
        "patron de nombres de archivo coincida con PATRON_NUMERO_ESCENA."
    )


def _crear_textclip_subtitulo(texto: str):
    return moviepy.TextClip(
        font=SUBTITULOS_FONT_PATH,
        text=texto,
        font_size=48,
        color="white",
        stroke_color="black",
        stroke_width=2,
        method="caption",
        size=(int(RESOLUCION_VIDEO.split("x")[0]) - 80, None),
    )


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    escenas = [e.model_dump() for e in estado.guion.escenas]

    if not escenas:
        raise ValueError("No hay escenas: corre primero el Depto 2 (Guion)")
    if not estado.audio.voz_path:
        raise ValueError("No hay voz_path: corre primero el Agente 4.1 (Locucion)")
    if not SUBTITULOS_FONT_PATH:
        raise RuntimeError(
            "SUBTITULOS_FONT_PATH no esta configurada en tu .env. MoviePy 2.x "
            "necesita una ruta real a un archivo .ttf/.otf para quemar los "
            "subtitulos (ej. C:\\Windows\\Fonts\\arialbd.ttf en Windows)."
        )
    if not Path(SUBTITULOS_FONT_PATH).exists():
        raise RuntimeError(f"Fuente no encontrada en disco: {SUBTITULOS_FONT_PATH}")

    resolucion = _parsear_resolucion(RESOLUCION_VIDEO)
    imagenes = _indexar_por_numero(estado.visual.imagenes)
    clips = _indexar_por_numero(estado.visual.clips_video)

    voz = AudioFileClip(estado.audio.voz_path)
    duraciones = calcular_duraciones_por_palabras(escenas, voz.duration)

    clips_escenas = []
    for escena in escenas:
        if shutdown_requested():
            raise RuntimeError("Shutdown solicitado durante ensamblaje de video")
        clips_escenas.append(
            _construir_clip_escena(escena, duraciones[escena["numero"]], imagenes, clips, resolucion)
        )
    video = concatenate_videoclips(clips_escenas, method="chain")

    pistas_audio = [voz]
    if estado.audio.musica_path:
        volumen_db = estado.audio.musica_volumen_db or -20.0
        factor_volumen = 10 ** (volumen_db / 20)
        musica = AudioFileClip(estado.audio.musica_path)
        musica = musica.with_effects([moviepy.vfx.Loop(duration=video.duration)]).with_volume_scaled(factor_volumen)
        pistas_audio.append(musica)
    video = video.with_audio(CompositeAudioClip(pistas_audio))

    if estado.audio.subtitulos_path:
        subtitulos = SubtitlesClip(estado.audio.subtitulos_path, make_textclip=_crear_textclip_subtitulo)
        subtitulos = subtitulos.with_position(("center", "bottom"))
        video = CompositeVideoClip([video, subtitulos], size=resolucion)

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    salida = SALIDA_DIR / f"{request.proyecto_id}_final.mp4"
    video = video.with_fps(FPS_VIDEO)
    video.write_videofile(str(salida), fps=FPS_VIDEO, codec="libx264", audio_codec="aac", logger=None)

    state.actualizar(request.proyecto_id, video_final_path=str(salida))
    return {"video_final_path": str(salida), "duracion_seg": video.duration, "num_escenas": len(escenas)}


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
