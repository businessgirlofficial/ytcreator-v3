"""
Agente 4.3 - Tecnico de subtitulos
Depto 4 (Audio)

FASE 4 - IMPLEMENTACION REAL
================================
Transcribe el voz.mp3 con Whisper pidiendo timestamps por PALABRA
(word_timestamps=True), y agrupa esas palabras en bloques cortos
(maximo 3 palabras por bloque, ideal para video dinamico/Shorts) para
generar el .srt final.

Confirmado contra el codigo fuente real de `openai-whisper`:
  modelo = whisper.load_model(nombre)
  resultado = modelo.transcribe(audio, language="es", word_timestamps=True)
  resultado["segments"][i]["words"][j] tiene "word", "start", "end"

El import de `whisper` es diferido (dentro de logica(), no a nivel de
modulo): asi el microservicio arranca bien aunque esa libreria pesada
(arrastra PyTorch) no este instalada en esta maquina, y solo falla
con un error claro cuando alguien de verdad intenta usarlo -- el
mismo patron que ya usamos para Kaggle.
"""

import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES, SUBTITULOS_PALABRAS_POR_BLOQUE, WHISPER_MODEL_SIZE
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "4.3_subtitulos"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Genera subtitulos cronometrados con Whisper en bloques cortos")
state = StateManager()

MAX_PALABRAS_POR_BLOQUE = SUBTITULOS_PALABRAS_POR_BLOQUE


def _formatear_timestamp_srt(segundos: float) -> str:
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    milisegundos = int(round((segundos - int(segundos)) * 1000))
    return f"{horas:02d}:{minutos:02d}:{segs:02d},{milisegundos:03d}"


def _agrupar_en_bloques_cortos(segmentos: list[dict], max_palabras: int = MAX_PALABRAS_POR_BLOQUE) -> list[dict]:
    """Aplana las palabras de todos los segmentos de Whisper y las agrupa
    en bloques cortos con su propio inicio/fin, ignorando los limites de
    'segmento' que trae Whisper por defecto (esos son frases completas,
    demasiado largas para subtitulos dinamicos)."""
    palabras = [w for seg in segmentos for w in seg.get("words", [])]

    bloques = []
    for i in range(0, len(palabras), max_palabras):
        grupo = palabras[i : i + max_palabras]
        if not grupo:
            continue
        texto = "".join(w.get("word", "") for w in grupo).strip()
        if not texto:
            continue
        bloques.append({"inicio": grupo[0]["start"], "fin": grupo[-1]["end"], "texto": texto})
    return bloques


OVERLAP_SEG = 0.3
_KEYWORDS_PROMINENCIA = re.compile(
    r"(?i)\b(importante|increíble|increible|atención|atencion|de repente|cuidado|secreto|peligro)\b"
)


def _aplicar_prominencia_y_overlap(bloques: list[dict]) -> list[dict]:
    """Ajusta end_times para prominencia visual y overlap anti-parpadeo."""
    for i, bloque in enumerate(bloques):
        texto = bloque["texto"]
        duracion = bloque["fin"] - bloque["inicio"]

        multiplicador = 1.0
        if len(texto) <= 15 and any(c in texto for c in "!?¡¿"):
            multiplicador = max(multiplicador, 1.5)
        elif len(texto) <= 20:
            multiplicador = max(multiplicador, 1.3)
        if _KEYWORDS_PROMINENCIA.search(texto):
            multiplicador = max(multiplicador, 1.3)

        if multiplicador > 1.0:
            bloque["fin"] = bloque["inicio"] + duracion * multiplicador

        bloque["fin"] += OVERLAP_SEG

        if i < len(bloques) - 1:
            limite = bloques[i + 1]["inicio"] + 0.1
            bloque["fin"] = min(bloque["fin"], limite)

    return bloques


def _generar_srt(bloques: list[dict]) -> str:
    lineas = []
    for i, b in enumerate(bloques, start=1):
        lineas.append(str(i))
        lineas.append(f"{_formatear_timestamp_srt(b['inicio'])} --> {_formatear_timestamp_srt(b['fin'])}")
        lineas.append(b["texto"])
        lineas.append("")
    return "\n".join(lineas)


PALABRAS_POR_SEGUNDO = 2.5


def _generar_srt_estimado(texto_completo: str, max_palabras: int = MAX_PALABRAS_POR_BLOQUE) -> tuple[str, int]:
    """Genera SRT con tiempos estimados a partir del texto, sin Whisper.
    Usa ~2.5 palabras/segundo como velocidad de narración promedio."""
    palabras = texto_completo.split()
    bloques = []
    cursor_seg = 0.0

    for i in range(0, len(palabras), max_palabras):
        grupo = palabras[i : i + max_palabras]
        texto_bloque = " ".join(grupo)
        duracion = len(grupo) / PALABRAS_POR_SEGUNDO
        bloques.append({
            "inicio": cursor_seg,
            "fin": cursor_seg + duracion,
            "texto": texto_bloque,
        })
        cursor_seg += duracion

    contenido = _generar_srt(bloques)
    return contenido, len(bloques)


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    voz_path = estado.audio.voz_path

    if not voz_path:
        raise ValueError("No hay voz_path en el estado: corre primero el Agente 4.1 (Locucion)")

    fuente = "whisper"
    fallback_reason = None

    try:
        import whisper

        modelo = whisper.load_model(WHISPER_MODEL_SIZE)
        resultado = modelo.transcribe(voz_path, language="es", word_timestamps=True)

        bloques = _agrupar_en_bloques_cortos(resultado.get("segments", []))
        if not bloques:
            raise ValueError("Whisper no devolvio palabras con timestamps")

        bloques = _aplicar_prominencia_y_overlap(bloques)
        contenido_srt = _generar_srt(bloques)
        num_bloques = len(bloques)
    except Exception as exc_whisper:
        fallback_reason = str(exc_whisper)
        fuente = "estimado"
        texto_completo = estado.guion.texto_completo
        if not texto_completo:
            raise ValueError(
                f"Whisper fallo ({exc_whisper}) y no hay texto de guion para generar SRT estimado"
            ) from exc_whisper
        contenido_srt, num_bloques = _generar_srt_estimado(texto_completo)

    subtitulos_path = str(Path(voz_path).with_name(Path(voz_path).stem + "_subtitulos.srt"))
    Path(subtitulos_path).write_text(contenido_srt, encoding="utf-8")

    state.actualizar(request.proyecto_id, audio={"subtitulos_path": subtitulos_path})
    resultado = {"subtitulos_path": subtitulos_path, "num_bloques": num_bloques, "fuente": fuente}
    if fallback_reason:
        resultado["fallback_reason"] = fallback_reason
    return resultado


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
