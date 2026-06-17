"""
Agente 4.2 - Productor musical
Depto 4 (Audio)

FASE 4 - IMPLEMENTACION REAL (con un hueco honesto que necesita tu input)
=============================================================================
La DECISION de fuente (Pixabay vs Suno) es real y deterministica: se
basa en si el mood del guion es uno "comun" con buena probabilidad de
match en un banco de stock, o uno especifico/inusual que se beneficia
de una pieza generada a medida.

LO QUE NO PUDE IMPLEMENTAR Y POR QUE:
  Busque la documentacion oficial de la API de Pixabay antes de
  escribir esto: cubre EXCLUSIVAMENTE imagenes y video
  ("RESTful interface for searching and retrieving royalty-free
  images and videos"). No hay un endpoint de musica documentado
  publicamente. Por eso _buscar_pixabay() esta marcado como
  pendiente -- necesito que me digas como tu sistema actual (Tab
  Audio de YTCreator Studio v3) obtiene musica de Pixabay realmente
  (scraping, un endpoint no documentado, descarga manual) para
  conectarlo aqui de verdad, en vez de adivinar un endpoint que
  podria no existir y romperse en silencio.

LO QUE SI IMPLEMENTE PARA SUNO:
  Suno no tiene una API publica oficial estable (tambien lo
  verifique): solo hay proveedores terceros no oficiales
  (sunoapi.org, api.box, evolink.ai, etc.), cada uno con su propio
  contrato. Implemente el patron generico mas comun entre ellos
  (generate -> poll -> descargar). Debes confirmar/ajustar
  SUNO_API_BASE_URL y los nombres de campo segun el proveedor que
  elijas -- no existe un unico "Suno API" universal al que apuntar.
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import httpx
import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES, SUNO_API_BASE_URL, SUNO_API_KEY
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "4.2_musica"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Elige o genera musica de fondo segun el mood")
state = StateManager()

# Un mood SIMPLE (una o dos palabras: "tenso", "calmado", "energetico")
# casi siempre tiene un buen match en un banco de stock como Pixabay.
# Un mood COMPUESTO/matizado (con conectores como "pero", "con", "y", o
# mas de 2 palabras: "nostalgico pero urgente") rara vez tiene un match
# exacto en stock -- se beneficia de una pieza generada a medida.
#
# Nota de diseno: probe primero con una lista fija de "moods comunes" y
# fallo en pruebas porque ese tipo de lista nunca esta completa (un mood
# tan basico como "tenso" no estaba en mi primera lista, pese a que el
# suspenso es una categoria enorme en cualquier banco de stock). Detectar
# la ESTRUCTURA del mood generaliza mejor que enumerar palabras.
CONECTORES_COMPUESTOS = (" pero ", " mas ", " y ", " con ", " que ", " sin ")


def _decidir_fuente(mood: str | None) -> str:
    if not mood:
        return "pixabay"
    mood_normalizado = mood.lower().strip()
    es_compuesto = (
        any(conector in mood_normalizado for conector in CONECTORES_COMPUESTOS)
        or len(mood_normalizado.split()) > 2
    )
    return "suno" if es_compuesto else "pixabay"


SUNO_POLL_INTERVAL_SEG = 15
SUNO_TIMEOUT_INTENTOS = 40


def _buscar_pixabay(mood: str) -> str:
    """PENDIENTE -- ver nota al inicio del archivo. La API publica de
    Pixabay no documenta busqueda de musica/audio."""
    raise NotImplementedError(
        "Busqueda de musica en Pixabay pendiente de confirmar: su API publica "
        "documentada (pixabay.com/api/docs/) cubre solo imagenes y video, no "
        "musica. Dime como tu sistema actual obtiene musica de Pixabay y lo "
        "conecto aqui correctamente."
    )


def _generar_suno(prompt_musical: str) -> str:
    if not SUNO_API_KEY:
        raise RuntimeError("SUNO_API_KEY no esta configurada en tu .env")
    if not SUNO_API_BASE_URL:
        raise RuntimeError(
            "SUNO_API_BASE_URL no esta configurada. Es la URL del proveedor no "
            "oficial de Suno que elijas (ej. https://api.sunoapi.org) -- no "
            "existe una unica API oficial de Suno a la que apuntar por default."
        )

    headers = {"Authorization": f"Bearer {SUNO_API_KEY}"}
    resp = httpx.post(
        f"{SUNO_API_BASE_URL}/api/v1/generate",
        headers=headers,
        json={"prompt": prompt_musical, "instrumental": True, "customMode": False},
        timeout=30,
    )
    resp.raise_for_status()
    task_id = resp.json().get("data", {}).get("taskId")
    if not task_id:
        raise RuntimeError(f"Respuesta inesperada del proveedor de Suno: {resp.text[:200]}")

    for _ in range(SUNO_TIMEOUT_INTENTOS):
        time.sleep(SUNO_POLL_INTERVAL_SEG)
        estado_resp = httpx.get(
            f"{SUNO_API_BASE_URL}/api/v1/generate/record-info",
            params={"taskId": task_id},
            headers=headers,
            timeout=30,
        )
        estado_resp.raise_for_status()
        datos = estado_resp.json().get("data", {})
        if datos.get("status") == "complete":
            audio_url = datos.get("audio_url")
            if not audio_url:
                raise RuntimeError("Suno marco la tarea como completa pero no devolvio audio_url")
            return audio_url
        if datos.get("status") == "error":
            raise RuntimeError(f"Suno fallo: {datos.get('error_message')}")

    raise TimeoutError("Suno no termino la generacion dentro del tiempo de espera")


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    mood = estado.estrategia.mood
    fuente = _decidir_fuente(mood)

    if fuente == "pixabay":
        musica_path = _buscar_pixabay(mood or "")
    else:
        musica_path = _generar_suno(f"background music, mood: {mood}, instrumental, no vocals, loopable")

    state.actualizar(
        request.proyecto_id,
        audio={"musica_path": musica_path, "musica_fuente": fuente, "musica_volumen_db": -20.0},
    )
    return {"mood": mood, "musica_fuente": fuente, "musica_path": musica_path}


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
