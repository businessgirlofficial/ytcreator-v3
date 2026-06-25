"""
Agente 1.4 - Generador de miniatura
Depto 1 (Estrategia)

Toma el miniatura_prompt que dejo el Director de Arte (1.3) y genera
la imagen real con FLUX.1-schnell via Hugging Face Inference API.

Maneja el caso de modelo cargando (status 503 con retry) y guarda
el .png final en STORAGE_DIR/miniaturas/{proyecto_id}_thumbnail.png.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES, STORAGE_DIR
from shared.hf_client import llamar_modelo
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "1.4_generador_miniatura"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Genera la imagen de miniatura con FLUX.1-schnell")
state = StateManager()

HF_FLUX_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"

SALIDA_DIR = Path(STORAGE_DIR) / "miniaturas"


def _generar_miniatura(prompt: str, proyecto_id: str) -> str:
    resp = llamar_modelo(HF_FLUX_URL, {"inputs": prompt})

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
