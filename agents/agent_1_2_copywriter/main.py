"""
Agente 1.2 - Copywriter viral
Depto 1 (Estrategia)

FASE 1 - IMPLEMENTACION REAL
================================
1. Le pide a Groq 10 titulos usando frameworks distintos (AIDA,
   brecha de curiosidad, contraintuitivo, listicle, FOMO), basados
   en el nicho y los patrones virales que dejo el Investigador (1.1).
2. VALIDA cada titulo programaticamente (no solo confia en el LLM):
   longitud ideal, sin duplicados, penalizacion si se sale del rango
   optimo de caracteres para YouTube.
3. Elige los 2 mejores: titulo_ganador y titulo_subcampeon.

Esto es justo la separacion que pediste: el LLM genera y se
autoevalua, pero la decision final de "cuales pasan" es codigo
determinista que puedes auditar y ajustar sin tocar el prompt.
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

AGENTE_ID = "1.2_copywriter"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Genera y valida titulos virales")
state = StateManager()

LONGITUD_MIN_IDEAL = 40
LONGITUD_MAX_IDEAL = 70

SYSTEM_PROMPT = """Eres un copywriter viral especializado en titulos de YouTube en espanol.
Conoces los frameworks: AIDA, brecha de curiosidad, contraintuitivo,
listicle numerico, urgencia/FOMO.

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "titulos": [
    {"texto": "...", "framework": "...", "score_creativo": 0-100},
    ... (exactamente 10 titulos, usando frameworks variados)
  ]
}

Reglas: cada titulo debe tener idealmente entre 40 y 70 caracteres,
ser ESPECIFICO al nicho dado (nada generico), y la promesa del
titulo debe ser cumplible por el contenido real (sin clickbait
enganoso)."""


def _validar_y_puntuar(titulos_raw: list[dict]) -> list[dict]:
    """Valida y re-puntua cada titulo con reglas deterministas, en codigo."""
    validados = []
    vistos = set()

    for t in titulos_raw:
        texto = (t.get("texto") or "").strip()
        if not texto or texto.lower() in vistos:
            continue
        vistos.add(texto.lower())

        score_creativo = float(t.get("score_creativo", 50))
        longitud = len(texto)

        if LONGITUD_MIN_IDEAL <= longitud <= LONGITUD_MAX_IDEAL:
            penalizacion = 0.0
        else:
            distancia = min(abs(longitud - LONGITUD_MIN_IDEAL), abs(longitud - LONGITUD_MAX_IDEAL))
            penalizacion = min(30.0, distancia * 0.8)

        score_final = max(0.0, round(score_creativo - penalizacion, 1))
        validados.append(
            {
                "texto": texto,
                "framework": t.get("framework", "desconocido"),
                "score_creativo": score_creativo,
                "longitud": longitud,
                "score_final": score_final,
            }
        )

    validados.sort(key=lambda x: x["score_final"], reverse=True)
    return validados


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    nicho = estado.estrategia.nicho
    patrones = estado.estrategia.patrones_virales

    if not nicho:
        raise ValueError("No hay nicho en el estado: corre primero el Agente 1.1 (Investigador)")

    patrones_texto = "\n".join(f"- {p}" for p in patrones) if patrones else "(ninguno detectado)"
    user_prompt = f"""Nicho: {nicho}

Patrones virales detectados para este nicho:
{patrones_texto}

Genera 10 titulos usando frameworks distintos."""

    resultado = generar_json(SYSTEM_PROMPT, user_prompt)
    titulos_raw = resultado.get("titulos", [])
    if not titulos_raw:
        raise ValueError("Groq no devolvio titulos en el formato esperado")

    validados = _validar_y_puntuar(titulos_raw)
    if not validados:
        raise ValueError("Ningun titulo paso la validacion (todos vacios o duplicados)")

    titulos_candidatos = [t["texto"] for t in validados]
    titulo_ganador = validados[0]["texto"]
    titulo_score = validados[0]["score_final"]
    titulo_subcampeon = validados[1]["texto"] if len(validados) > 1 else None

    state.actualizar(
        request.proyecto_id,
        estrategia={
            "titulos_candidatos": titulos_candidatos,
            "titulo_ganador": titulo_ganador,
            "titulo_score": titulo_score,
            "titulo_subcampeon": titulo_subcampeon,
        },
    )
    return {
        "titulos_validados": validados,
        "titulo_ganador": titulo_ganador,
        "titulo_subcampeon": titulo_subcampeon,
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
