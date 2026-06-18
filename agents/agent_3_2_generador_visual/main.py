"""
Agente 3.2 - Generador visual
Depto 3 (Visual)

FASE 3 - IMPLEMENTACION REAL (mecanica de Kaggle confirmada + contrato pendiente de tu confirmacion)
========================================================================================================
Sube los prompts de 3.1 como nueva version de un dataset de Kaggle,
dispara la ejecucion remota del notebook YouTube AI Studio v7 (GPU
T4 x2), espera a que termine, y descarga las imagenes/clips generados.

LO QUE SI ESTA CONFIRMADO (probado contra la libreria oficial `kaggle`
version 2.2.2, metodos y firmas reales, no adivinados):
  - autenticacion con KAGGLE_USERNAME + KAGGLE_KEY
  - subir nueva version de dataset (dataset_create_version)
  - disparar ejecucion de kernel (kernels_push)
  - sondear estado (kernels_status) hasta "complete"
  - descargar archivos de salida (kernels_output)

LO QUE TU DEBES CONFIRMAR/AJUSTAR (no tengo acceso al codigo de tu
notebook v7 real):
  1. KAGGLE_DATASET_SLUG y KAGGLE_KERNEL_SLUG en tu .env deben
     apuntar a tu dataset y notebook reales (no a los nombres
     genericos que puse de default).
  2. Tu notebook debe LEER los prompts desde
     /kaggle/input/<dataset-slug>/prompts.json -- si hoy no lo hace,
     hay que agregarle esa celda.
  3. Tu notebook debe ESCRIBIR los .png/.mp4 finales en su carpeta de
     output normal de Kaggle, para que kernels_output los descargue.
  4. Debe existir una carpeta local kaggle_kernel_meta/ con un
     kernel-metadata.json valido apuntando a KAGGLE_KERNEL_SLUG
     (la API de Kaggle lo exige para poder hacer kernels_push).
"""

import json
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import KAGGLE_DATASET_SLUG, KAGGLE_KERNEL_SLUG, REGISTRO_AGENTES, STORAGE_DIR
from shared.kaggle_client import descargar_resultados, estado_kernel, lanzar_kernel, subir_dataset
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "3.2_generador_visual"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Ejecuta generacion hibrida de imagenes y video en Kaggle")
state = StateManager()

POLL_INTERVAL_SEG = 30
TIMEOUT_SEG = 60 * 60 * 2  # 2 horas de margen (GPU T4 x2, tier gratuito)

STAGING_DIR = Path(STORAGE_DIR) / "kaggle_staging"
OUTPUT_DIR = Path(STORAGE_DIR) / "kaggle_outputs"
KERNEL_META_DIR = Path("kaggle_kernel_meta")


def _preparar_dataset(proyecto_id: str, escenas: list[dict]) -> Path:
    carpeta = STAGING_DIR / proyecto_id
    carpeta.mkdir(parents=True, exist_ok=True)

    payload = {
        "proyecto_id": proyecto_id,
        "escenas": [
            {"numero": e["numero"], "prompt": e.get("prompt_visual"), "usa_video_ia": e.get("usa_video_ia", False)}
            for e in escenas
        ],
    }
    (carpeta / "prompts.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    metadata = {"title": "ytcreator-prompts", "id": KAGGLE_DATASET_SLUG, "licenses": [{"name": "CC0-1.0"}]}
    (carpeta / "dataset-metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return carpeta


def _esperar_kernel() -> None:
    transcurrido = 0
    while transcurrido < TIMEOUT_SEG:
        status, error_msg = estado_kernel(KAGGLE_KERNEL_SLUG)
        if status and "complete" in status.lower():
            return
        if status and ("error" in status.lower() or "cancel" in status.lower()):
            raise RuntimeError(f"El kernel de Kaggle termino con error: {error_msg or status}")
        time.sleep(POLL_INTERVAL_SEG)
        transcurrido += POLL_INTERVAL_SEG
    raise TimeoutError(f"El kernel no termino dentro de {TIMEOUT_SEG // 60} minutos")


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)

    if not estado.visual.prompts_generados or not estado.guion.escenas:
        raise ValueError("No hay prompts listos: corre primero el Agente 3.1 (Prompt Maker)")

    escenas = [e.model_dump() for e in estado.guion.escenas]

    carpeta_dataset = _preparar_dataset(request.proyecto_id, escenas)
    subir_dataset(str(carpeta_dataset))
    lanzar_kernel(str(KERNEL_META_DIR))
    _esperar_kernel()

    destino = OUTPUT_DIR / request.proyecto_id
    destino.mkdir(parents=True, exist_ok=True)
    archivos = descargar_resultados(KAGGLE_KERNEL_SLUG, str(destino))

    imagenes = sorted(str(p) for p in destino.glob("*.png"))
    clips_video = sorted(str(p) for p in destino.glob("*.mp4"))

    state.actualizar(request.proyecto_id, visual={"imagenes": imagenes, "clips_video": clips_video})
    return {
        "imagenes_generadas": len(imagenes),
        "clips_generados": len(clips_video),
        "archivos_descargados": len(archivos),
        "carpeta_salida": str(destino),
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
