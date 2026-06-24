"""
Agente 1.4 - Generador de miniatura
Depto 1 (Estrategia)

Toma el miniatura_prompt que dejo el Director de Arte (1.3) y genera
la imagen real con FLUX.1-schnell via Hugging Face Inference API.

Maneja el caso de modelo cargando (status 503 con retry) y guarda
el .png final en STORAGE_DIR/miniaturas/{proyecto_id}_thumbnail.png.
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import httpx
import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import HF_API_TOKEN, REGISTRO_AGENTES, STORAGE_DIR
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "1.4_generador_miniatura"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Genera la imagen de miniatura con FLUX.1-schnell")
state = StateManager()

HF_FLUX_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
HF_MAX_ESPERA_CARGA = 120
HF_POLL_INTERVAL = 10

SALIDA_DIR = Path(STORAGE_DIR) / "miniaturas"


def _generar_miniatura(prompt: str, proyecto_id: str) -> str:
    if not HF_API_TOKEN:
        raise RuntimeError(
            "HF_API_TOKEN no esta configurada. Generala gratis en "
            "huggingface.co/settings/tokens"
        )

    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}

    esperado = 0
    while esperado < HF_MAX_ESPERA_CARGA:
        resp = httpx.post(
            HF_FLUX_URL,
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
            raise RuntimeError("FLUX.1-schnell: rate limit de HF alcanzado")

        resp.raise_for_status()
        break
    else:
        raise RuntimeError(
            f"FLUX.1-schnell: el modelo no termino de cargar tras {HF_MAX_ESPERA_CARGA}s"
        )

    SALIDA_DIR.mkdir(parents=True, exist_ok=True)
    destino = SALIDA_DIR / f"{proyecto_id}_thumbnail.png"
    destino.write_bytes(resp.content)

    return str(destino)


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    prompt = estado.estrategia.miniatura_prompt

    if not prompt:
        raise ValueError(
            "No hay miniatura_prompt en el estado: corre primero el "
            "Agente 1.3 (Director de Arte)"
        )

    try:
        miniatura_path = _generar_miniatura(prompt, request.proyecto_id)
    except Exception as exc:
        state.actualizar(
            request.proyecto_id,
            estrategia={"miniatura_path": None},
        )
        return {
            "miniatura_path": None,
            "miniatura_prompt": prompt,
            "skipped_reason": str(exc),
        }

    state.actualizar(
        request.proyecto_id,
        estrategia={"miniatura_path": miniatura_path},
    )
    return {"miniatura_path": miniatura_path}


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
