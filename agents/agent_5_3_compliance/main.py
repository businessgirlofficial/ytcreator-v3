"""
Agente 5.3 - Compliance YouTube
Depto 5 (Cierre)

Ultima puerta del pipeline. Evalua el video completo (titulo, guion,
descripcion, tags, miniatura) contra las politicas oficiales de YouTube
contenidas en knowledge/youtube_policies.md.

Produce un nivel de riesgo:
  - critico: bloquea el pipeline (el sub-orquestador no marca completado)
  - alto: warnings fuertes, deja pasar (decision humana)
  - medio/bajo: sugerencias informativas

Categorias de evaluacion:
  1. Community Guidelines (discurso de odio, acoso, violencia, etc.)
  2. Monetizacion (contenido apto para anunciantes)
  3. Spam y practicas enganosas (clickbait, keyword stuffing, etc.)
  4. Copyright y contenido IA
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES
from shared.groq_client import generar_json
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "5.3_compliance"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Verifica compliance con politicas de YouTube")
state = StateManager()

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"
POLICIES_PATH = KNOWLEDGE_DIR / "youtube_policies.md"

SYSTEM_PROMPT = """Eres un auditor de compliance especializado en las politicas de YouTube.
Tu trabajo es proteger el canal de sanciones, perdida de monetizacion y
strikes. Eres exhaustivo y conservador: si hay duda, marcas warning.

Se te proporcionan las politicas oficiales de YouTube y el contenido
completo de un video (titulo, guion, descripcion, tags, miniatura).

Evalua el video contra CADA categoria de las politicas y responde en
JSON valido con este formato exacto:

{
  "nivel_riesgo": "bajo|medio|alto|critico",
  "aprobado": true/false,
  "warnings": [
    {
      "categoria": "nombre de la categoria (ej: monetizacion, community_guidelines, spam, copyright, contenido_ia)",
      "severidad": "info|advertencia|grave|critico",
      "detalle": "que regla especifica se esta violando o podria violarse",
      "sugerencia": "como corregirlo para cumplir con las politicas"
    }
  ],
  "resumen": "evaluacion general en 2-3 frases"
}

REGLAS DE DECISION:
- nivel_riesgo "critico": el contenido viola directamente una politica
  que resultaria en strike, remocion del video o terminacion del canal.
  aprobado DEBE ser false.
- nivel_riesgo "alto": el contenido esta en zona gris o podria activar
  revision manual de YouTube. Hay riesgo real de desmonetizacion o
  restriccion. aprobado es true (decision humana) pero con warnings graves.
- nivel_riesgo "medio": el contenido podria recibir "limited ads" o
  tiene elementos que conviene ajustar para maximizar monetizacion.
  aprobado es true.
- nivel_riesgo "bajo": el contenido cumple con todas las politicas.
  aprobado es true. warnings puede estar vacio o tener sugerencias menores.

IMPORTANTE:
- Evalua SIEMPRE si el titulo corresponde al contenido real del guion
  (clickbait enganoso es sancionable)
- Verifica que los tags correspondan al contenido real
- Considera que este es contenido generado con IA: verifica si necesita
  divulgacion segun las politicas de YouTube sobre contenido sintetico
- Se conservador con monetizacion: es mejor advertir que perder ingresos"""


def _cargar_politicas() -> str:
    if not POLICIES_PATH.exists():
        raise FileNotFoundError(
            f"No se encontro {POLICIES_PATH}. El archivo de politicas es requerido."
        )
    return POLICIES_PATH.read_text(encoding="utf-8")


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)

    if not estado.guion.texto_completo:
        raise ValueError("No hay guion para evaluar: corre primero el Depto 2")

    politicas = _cargar_politicas()

    escenas_texto = "\n".join(
        f"[{e.tipo.upper()}] {e.texto}" for e in estado.guion.escenas
    )

    contenido_video = f"""TITULO: {estado.estrategia.titulo_ganador or "sin titulo"}

GUION COMPLETO (por escenas):
{escenas_texto}

DESCRIPCION YOUTUBE:
{estado.metadata.descripcion or "no generada aun"}

TAGS:
{", ".join(estado.metadata.tags) if estado.metadata.tags else "no generados aun"}

CATEGORIA:
{estado.metadata.categoria or "no asignada"}

PROMPT DE MINIATURA:
{estado.estrategia.miniatura_prompt or "no generado"}

COMPOSICION DE MINIATURA:
{estado.estrategia.miniatura_composicion or "no definida"}

NOTA: Este video fue generado completamente con IA (guion por LLM,
imagenes por Stable Diffusion/FLUX, voz por TTS, musica por MusicGen/Pixabay)."""

    user_prompt = f"""POLITICAS DE YOUTUBE:
{politicas}

---

CONTENIDO DEL VIDEO A EVALUAR:
{contenido_video}"""

    resultado = generar_json(SYSTEM_PROMPT, user_prompt, temperatura=0.2)

    nivel = resultado.get("nivel_riesgo", "bajo")
    aprobado = resultado.get("aprobado", True)
    warnings = resultado.get("warnings", [])

    if nivel == "critico":
        aprobado = False

    state.actualizar(
        request.proyecto_id,
        compliance={
            "nivel_riesgo": nivel,
            "aprobado": aprobado,
            "warnings": warnings,
            "resumen": resultado.get("resumen", ""),
        },
    )

    return {
        "nivel_riesgo": nivel,
        "aprobado": aprobado,
        "warnings": warnings,
        "resumen": resultado.get("resumen", ""),
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
