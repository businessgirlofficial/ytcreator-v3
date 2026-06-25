"""
Agente 4.1 - Director de locucion
Depto 4 (Audio)

FASE 4 - IMPLEMENTACION REAL
================================
Genera la narracion completa con Edge TTS. La voz y el rate (velocidad)
se eligen en CODIGO (no con Groq -- es una decision determinista de
catalogo, no creativa) a partir del canal_tono que dejo el Depto 1.

Simplificacion deliberada: se genera UN solo audio para todo el guion
(no uno por escena). Variar el rate escena por escena requeriria
generar clips separados y empalmarlos, lo cual puede introducir
"costuras" audibles en el audio -- mas seguro y natural empezar con
una sola pasada con un rate global coherente con el tono del canal.

Confirmado contra el codigo real de la libreria `edge-tts` 7.2.8:
Communicate(texto, voz, rate=..., pitch=...).save_sync(path) -- sin
necesidad de manejar asyncio manualmente.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES, STORAGE_DIR
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "4.1_locucion"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Genera la narracion con Edge TTS")
state = StateManager()

SALIDA_DIR = Path(STORAGE_DIR) / "audio"

# Catalogo de voces conocidas y estables de Edge TTS para espanol
# latinoamericano. Si tu canal_tono no calza con ninguna clave, se usa
# la voz "default".
VOZ_CATALOGO = {
    "educativo": "es-CO-GonzaloNeural",
    "serio": "es-CO-GonzaloNeural",
    "entretenimiento": "es-MX-DaliaNeural",
    "rapido": "es-MX-DaliaNeural",
    "default": "es-CO-SalomeNeural",
}


def _elegir_voz(canal_tono: str | None) -> str:
    if not canal_tono:
        return VOZ_CATALOGO["default"]
    tono = canal_tono.lower()
    for clave, voz in VOZ_CATALOGO.items():
        if clave != "default" and clave in tono:
            return voz
    return VOZ_CATALOGO["default"]


def _elegir_rate(canal_tono: str | None) -> str:
    if not canal_tono:
        return "+0%"
    tono = canal_tono.lower()
    if "rapido" in tono or "entretenimiento" in tono:
        return "+10%"
    if "serio" in tono or "calmado" in tono:
        return "-5%"
    return "+0%"


def _generar_edge_tts(texto: str, voz_id: str, rate: str, pitch: str, salida: Path) -> None:
    import edge_tts
    comunicador = edge_tts.Communicate(texto, voz_id, rate=rate, pitch=pitch)
    comunicador.save_sync(str(salida))


def _generar_gtts(texto: str, salida: Path) -> None:
    from gtts import gTTS
    tts = gTTS(text=texto, lang="es", slow=False)
    tts.save(str(salida))


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    texto = estado.guion.texto_completo

    if not texto:
        raise ValueError("No hay guion: corre primero el Depto 2 (Guion)")

    voz_id = _elegir_voz(estado.estrategia.canal_tono)
    rate = _elegir_rate(estado.estrategia.canal_tono)
    pitch = "+0Hz"

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    salida = SALIDA_DIR / f"{request.proyecto_id}_voz.mp3"

    fuente = "edge_tts"
    fallback_reason = None

    try:
        _generar_edge_tts(texto, voz_id, rate, pitch, salida)
    except Exception as exc_edge:
        fallback_reason = str(exc_edge)
        try:
            _generar_gtts(texto, salida)
            fuente = "gtts"
        except Exception as exc_gtts:
            raise RuntimeError(
                f"TTS fallo con ambos proveedores. "
                f"edge-tts: {exc_edge} | gTTS: {exc_gtts}"
            ) from exc_gtts

    voz_config = {"voice_id": voz_id if fuente == "edge_tts" else "gtts_es", "rate": rate, "pitch": pitch}
    state.actualizar(
        request.proyecto_id,
        audio={"voz_path": str(salida), "voz_config": voz_config},
    )
    resultado = {"voz_path": str(salida), "voz_config": voz_config, "fuente": fuente}
    if fallback_reason:
        resultado["fallback_reason"] = fallback_reason
    return resultado


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
