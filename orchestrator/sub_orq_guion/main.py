"""
Sub-orquestador - Depto 2 (Guion)

Coordina el ciclo completo de escritura y evaluacion del guion:
  Guionista (2.1) -> Evaluacion -> Reescritura si no aprueba

A diferencia de los otros sub-orquestadores que solo encadenan agentes,
este absorbe la logica de evaluacion directamente (lo que antes era el
agente 2.2). La razon: evaluar y decidir si reescribir es una decision
de orquestacion, no una tarea de un agente individual.

La evaluacion combina dos cosas:
  - Score cualitativo de Groq en 4 dimensiones (hook, ritmo, CTA, coherencia)
  - Penalizaciones deterministas por reglas estructurales (en codigo)
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import httpx
import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES, url_agente
from shared.groq_client import generar_json
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "sub_orq_guion"
app: FastAPI = crear_agente_app(
    AGENTE_ID, descripcion="Orquesta escritura, evaluacion y reescritura del guion"
)
state = StateManager()

MAX_REINTENTOS_GUION = 3
MAX_REINTENTOS_AGENTE = 3
BACKOFF_BASE = 5
UMBRAL_APROBACION = 80.0
MINIMO_ESCENAS_CUERPO = 5

SYSTEM_PROMPT_EVALUACION = """Eres un evaluador critico de guiones virales de YouTube,
especializado en retencion de audiencia. Trabajas en espanol y eres
exigente: tu trabajo es detectar debilidades reales, no halagar.

Evalua el guion en 4 dimensiones, cada una de 0 a 25 puntos:
- fuerza_hook: que tan fuerte es la tension/curiosidad en los primeros segundos
- ritmo: si cada escena mantiene el interes y no hay caidas
- claridad_cta: si el cierre motiva una accion clara y especifica
- coherencia_titulo: si el contenido cumple la promesa del titulo
  (sin ser clickbait enganoso)

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "fuerza_hook": 0-25,
  "ritmo": 0-25,
  "claridad_cta": 0-25,
  "coherencia_titulo": 0-25,
  "feedback": "critica especifica y accionable, maximo 3 frases, sobre que reescribir exactamente"
}"""


def _llamar_guionista(request: AgenteRequest) -> dict:
    ultimo_error = None
    for intento in range(1, MAX_REINTENTOS_AGENTE + 1):
        try:
            resp = httpx.post(
                f"{url_agente('2.1_guionista')}/ejecutar",
                json=request.model_dump(),
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("estado") == "error":
                raise RuntimeError(f"2.1_guionista fallo: {data.get('error')}")
            return data
        except Exception as exc:
            ultimo_error = exc
            if intento < MAX_REINTENTOS_AGENTE:
                time.sleep(BACKOFF_BASE * intento)
    raise RuntimeError(f"2.1_guionista fallo tras {MAX_REINTENTOS_AGENTE} intentos: {ultimo_error}")


def _validar_estructura(escenas: list[dict]) -> tuple[float, list[str]]:
    penalizacion = 0.0
    problemas = []
    tipos = [e.get("tipo") for e in escenas]

    if "hook" not in tipos:
        penalizacion += 20
        problemas.append("falta una escena de tipo hook al inicio")

    num_cuerpo = tipos.count("cuerpo")
    if num_cuerpo < MINIMO_ESCENAS_CUERPO:
        faltantes = MINIMO_ESCENAS_CUERPO - num_cuerpo
        penalizacion += faltantes * 4
        problemas.append(
            f"el cuerpo tiene solo {num_cuerpo} escena(s), deberian ser al menos {MINIMO_ESCENAS_CUERPO}"
        )

    if not escenas or escenas[-1].get("tipo") != "cta":
        penalizacion += 15
        problemas.append("la ultima escena debe ser el CTA de cierre")

    if tipos.count("cta") != 1:
        penalizacion += 10
        problemas.append("debe haber exactamente una escena de tipo CTA")

    return penalizacion, problemas


def _evaluar_guion(proyecto_id: str) -> dict:
    estado = state.leer(proyecto_id)
    guion = estado.guion

    if not guion.texto_completo or not guion.escenas:
        raise ValueError("No hay guion para evaluar")

    escenas = [e.model_dump() for e in guion.escenas]
    texto_escenas = "\n".join(f"[{e['tipo'].upper()}] {e['texto']}" for e in escenas)

    user_prompt = f"""Titulo del video: {estado.estrategia.titulo_ganador}

Guion a evaluar (por escenas):
{texto_escenas}"""

    resultado = generar_json(SYSTEM_PROMPT_EVALUACION, user_prompt, temperatura=0.3)

    score_groq = sum(
        float(resultado.get(campo, 0))
        for campo in ("fuerza_hook", "ritmo", "claridad_cta", "coherencia_titulo")
    )
    feedback_groq = resultado.get("feedback", "")

    penalizacion_estructural, problemas_estructurales = _validar_estructura(escenas)
    score_final = max(0.0, round(score_groq - penalizacion_estructural, 1))
    aprobado = score_final >= UMBRAL_APROBACION

    if aprobado:
        feedback_final = ""
    else:
        partes = [feedback_groq] if feedback_groq else []
        partes.extend(problemas_estructurales)
        feedback_final = " | ".join(partes)

    intentos_previos = guion.intentos_reescritura
    state.actualizar(
        proyecto_id,
        guion={
            "score": score_final,
            "aprobado": aprobado,
            "feedback_evaluador": feedback_final,
            "intentos_reescritura": intentos_previos if aprobado else intentos_previos + 1,
        },
    )
    return {
        "score_groq": score_groq,
        "penalizacion_estructural": penalizacion_estructural,
        "score_final": score_final,
        "aprobado": aprobado,
        "feedback": feedback_final,
    }


def logica(request: AgenteRequest) -> dict:
    intentos = 0
    while intentos < MAX_REINTENTOS_GUION:
        _llamar_guionista(request)
        resultado_eval = _evaluar_guion(request.proyecto_id)

        if resultado_eval["aprobado"]:
            return {
                "aprobado": True,
                "intentos_totales": intentos + 1,
                "score_final": resultado_eval["score_final"],
            }
        intentos += 1

    return {
        "aprobado": False,
        "intentos_totales": MAX_REINTENTOS_GUION,
        "score_final": resultado_eval["score_final"],
        "feedback": resultado_eval["feedback"],
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
