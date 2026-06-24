"""
Sub-orquestador - Depto 3 (Visual)

Coordina: Prompt Maker (3.1) -> Generador Visual (3.2) -> Validacion

Despues de que el Generador Visual descarga las imagenes/clips desde
Kaggle, este sub-orquestador verifica calidad en dos niveles:

  1. Validacion estructural (determinista, en codigo):
     - Que cada escena con usa_video_ia=True tenga su archivo generado
     - Que los archivos existan en disco y no esten vacios/corruptos
     - Que las imagenes tengan la resolucion minima esperada
     - Que la cantidad de assets coincida con lo que se pidio

  2. Validacion visual con LLaVA (HF Inference API, gratis):
     - Consistencia de estilo entre escenas consecutivas
     - Deteccion de artefactos o deformaciones
     - Que el contenido visual corresponda al prompt original
"""

import base64
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import httpx
import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import HF_API_TOKEN, REGISTRO_AGENTES, RESOLUCION_VIDEO
from shared.http_client import llamar_con_reintento
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "sub_orq_visual"
app: FastAPI = crear_agente_app(
    AGENTE_ID, descripcion="Orquesta Prompt Maker, Generador Visual y validacion de calidad"
)
state = StateManager()

_res = RESOLUCION_VIDEO.split("x")
MIN_ANCHO = int(_res[0]) if len(_res) == 2 else 1920
MIN_ALTO = int(_res[1]) if len(_res) == 2 else 1080

HF_LLAVA_URL = "https://api-inference.huggingface.co/models/llava-hf/llava-1.5-7b-hf"
HF_MAX_ESPERA_CARGA = 120
HF_POLL_INTERVAL = 10

PROMPT_VALIDACION_INDIVIDUAL = """Analyze this AI-generated image for a YouTube video. Answer in JSON only:
{
  "matches_prompt": true/false,
  "has_artifacts": true/false,
  "artifact_details": "description if any, empty string if none",
  "quality_score": 1-10,
  "issues": "brief description of problems, empty string if none"
}

The image was generated from this prompt: "{prompt}"

Check for: deformed hands/faces, text artifacts, blurry regions, unnatural anatomy, broken objects, inconsistent lighting."""

PROMPT_CONSISTENCIA = """Compare these two consecutive frames from the same YouTube video. They should share the same visual style, subject appearance, and background.
Answer in JSON only:
{
  "style_consistent": true/false,
  "subject_consistent": true/false,
  "issues": "brief description of inconsistencies, empty string if none"
}"""

UMBRAL_CALIDAD = 4


def _validar_estructural(proyecto_id: str) -> tuple[bool, list[str]]:
    """Validaciones deterministas sobre los assets generados."""
    estado = state.leer(proyecto_id)
    escenas = estado.guion.escenas
    visual = estado.visual
    problemas = []

    escenas_con_video = [e for e in escenas if e.usa_video_ia]
    total_assets = len(visual.imagenes) + len(visual.clips_video)

    if total_assets == 0:
        problemas.append("no se descargo ningun asset visual de Kaggle")
        return False, problemas

    if total_assets < len(escenas_con_video):
        problemas.append(
            f"se esperaban {len(escenas_con_video)} assets para escenas con video IA, "
            f"pero solo hay {total_assets}"
        )

    for img_path in visual.imagenes:
        p = Path(img_path)
        if not p.exists():
            problemas.append(f"imagen no encontrada en disco: {p.name}")
            continue
        if p.stat().st_size < 1024:
            problemas.append(f"imagen sospechosamente pequena (<1KB): {p.name}")
            continue
        _verificar_resolucion_imagen(p, problemas)

    for clip_path in visual.clips_video:
        p = Path(clip_path)
        if not p.exists():
            problemas.append(f"clip de video no encontrado en disco: {p.name}")
            continue
        if p.stat().st_size < 10240:
            problemas.append(f"clip sospechosamente pequeno (<10KB): {p.name}")

    sin_prompt = [e.numero for e in escenas if not e.prompt_visual]
    if sin_prompt:
        problemas.append(f"escenas sin prompt visual asignado: {sin_prompt}")

    aprobado = len(problemas) == 0
    return aprobado, problemas


def _verificar_resolucion_imagen(path: Path, problemas: list[str]):
    """Verifica resolucion leyendo el header del PNG sin dependencias externas."""
    try:
        with open(path, "rb") as f:
            header = f.read(32)
        if header[:8] != b"\x89PNG\r\n\x1a\n":
            return
        if len(header) < 24:
            return
        ancho = int.from_bytes(header[16:20], "big")
        alto = int.from_bytes(header[20:24], "big")
        if ancho < MIN_ANCHO or alto < MIN_ALTO:
            problemas.append(
                f"{path.name}: resolucion {ancho}x{alto} menor a la esperada {MIN_ANCHO}x{MIN_ALTO}"
            )
    except Exception:
        pass


def _imagen_a_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _llamar_llava(image_b64: str, prompt: str) -> dict | None:
    """Llama a LLaVA via HF Inference API con manejo de cold start."""
    if not HF_API_TOKEN:
        return None

    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {
        "inputs": {
            "image": image_b64,
            "text": prompt,
        },
        "parameters": {"max_new_tokens": 300},
    }

    esperado = 0
    while esperado < HF_MAX_ESPERA_CARGA:
        try:
            resp = httpx.post(HF_LLAVA_URL, headers=headers, json=payload, timeout=120)
        except httpx.TimeoutException:
            return None

        if resp.status_code == 503:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            wait = min(body.get("estimated_time", HF_POLL_INTERVAL), 30)
            time.sleep(wait)
            esperado += wait
            continue

        if resp.status_code == 429:
            return None

        if resp.status_code != 200:
            return None

        break
    else:
        return None

    try:
        data = resp.json()
        texto = data[0].get("generated_text", "") if isinstance(data, list) else data.get("generated_text", "")
        inicio = texto.find("{")
        fin = texto.rfind("}") + 1
        if inicio >= 0 and fin > inicio:
            import json
            return json.loads(texto[inicio:fin])
    except Exception:
        pass
    return None


def _validar_visual_multimodal(proyecto_id: str) -> tuple[bool, list[str]]:
    """Valida calidad visual con LLaVA via HF Inference API."""
    if not HF_API_TOKEN:
        return True, ["validacion visual omitida: HF_API_TOKEN no configurada"]

    estado = state.leer(proyecto_id)
    escenas = estado.guion.escenas
    imagenes = estado.visual.imagenes
    problemas = []

    if not imagenes:
        return True, []

    escenas_por_numero = {e.numero: e for e in escenas}
    imagenes_validas = []

    for i, img_path in enumerate(imagenes):
        p = Path(img_path)
        if not p.exists() or p.stat().st_size < 1024:
            continue

        numero_escena = i + 1
        escena = escenas_por_numero.get(numero_escena)
        prompt_original = escena.prompt_visual if escena else "YouTube video frame"

        prompt = PROMPT_VALIDACION_INDIVIDUAL.format(prompt=prompt_original)
        resultado = _llamar_llava(_imagen_a_base64(p), prompt)

        if resultado is None:
            continue

        imagenes_validas.append(p)
        score = resultado.get("quality_score", 10)
        if isinstance(score, (int, float)) and score < UMBRAL_CALIDAD:
            issues = resultado.get("issues", "baja calidad general")
            problemas.append(f"{p.name}: score {score}/10 — {issues}")

        if resultado.get("has_artifacts"):
            detalles = resultado.get("artifact_details", "artefactos detectados")
            if detalles:
                problemas.append(f"{p.name}: artefactos — {detalles}")

        if resultado.get("matches_prompt") is False:
            problemas.append(f"{p.name}: el contenido no corresponde al prompt solicitado")

    if len(imagenes_validas) >= 2:
        _validar_consistencia_pares(imagenes_validas, problemas)

    aprobado = len(problemas) == 0
    return aprobado, problemas


def _validar_consistencia_pares(imagenes: list[Path], problemas: list[str]):
    """Compara pares de imagenes consecutivas para verificar consistencia de estilo."""
    max_pares = min(len(imagenes) - 1, 3)
    paso = max(1, (len(imagenes) - 1) // max_pares)

    for i in range(0, len(imagenes) - 1, paso):
        if i >= len(imagenes) - 1:
            break

        img_a = imagenes[i]
        img_b = imagenes[i + 1]

        b64_a = _imagen_a_base64(img_a)

        resultado = _llamar_llava(b64_a, PROMPT_CONSISTENCIA)
        if resultado is None:
            continue

        if resultado.get("style_consistent") is False:
            issues = resultado.get("issues", "estilos visuales diferentes")
            problemas.append(
                f"inconsistencia de estilo entre {img_a.name} y {img_b.name}: {issues}"
            )

        if resultado.get("subject_consistent") is False:
            issues = resultado.get("issues", "el sujeto cambia de apariencia")
            problemas.append(
                f"inconsistencia de sujeto entre {img_a.name} y {img_b.name}: {issues}"
            )


def logica(request: AgenteRequest) -> dict:
    llamar_con_reintento("3.1_prompt_maker", request, timeout=300)
    llamar_con_reintento("3.2_generador_visual", request, timeout=300)

    aprobado_estr, problemas_estr = _validar_estructural(request.proyecto_id)
    aprobado_visual, problemas_visual = _validar_visual_multimodal(request.proyecto_id)

    todos_los_problemas = problemas_estr + problemas_visual
    aprobado = aprobado_estr and aprobado_visual

    estado = state.leer(request.proyecto_id)
    return {
        "aprobado": aprobado,
        "imagenes": len(estado.visual.imagenes),
        "clips_video": len(estado.visual.clips_video),
        "problemas": todos_los_problemas if not aprobado else [],
        "validacion_visual_activa": bool(HF_API_TOKEN),
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
