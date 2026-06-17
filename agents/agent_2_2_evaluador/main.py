"""
Agente 2.2 - Evaluador de guion
Depto 2 (Guion)

FASE 2 - IMPLEMENTACION REAL
================================
Evalua el guion en 4 dimensiones con Groq (fuerza del hook, ritmo,
claridad del CTA, coherencia con el titulo) y ADEMAS aplica reglas
estructurales deterministas en codigo (que exista un hook, que el
cuerpo tenga al menos 5 escenas, que el CTA sea la ultima escena y
que haya exactamente una).

El score final combina ambas cosas: la evaluacion cualitativa de
Groq menos las penalizaciones estructurales. Esto evita que un guion
estructuralmente roto pase solo porque "se lee bien".

El feedback que se guarda si NO se aprueba es justo lo que el
Guionista (2.1) lee en su siguiente intento para reescribir.
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

AGENTE_ID = "2.2_evaluador"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Puntua el guion y decide si se aprueba")
state = StateManager()

UMBRAL_APROBACION = 80.0
MINIMO_ESCENAS_CUERPO = 5

SYSTEM_PROMPT = """Eres un evaluador critico de guiones virales de YouTube,
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


def _validar_estructura(escenas: list[dict]) -> tuple[float, list[str]]:
    """Reglas deterministas que el LLM no decide. Devuelve (penalizacion, problemas)."""
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


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    guion = estado.guion

    if not guion.texto_completo or not guion.escenas:
        raise ValueError("No hay guion para evaluar: corre primero el Agente 2.1 (Guionista)")

    escenas = [e.model_dump() for e in guion.escenas]
    texto_escenas = "\n".join(f"[{e['tipo'].upper()}] {e['texto']}" for e in escenas)

    user_prompt = f"""Titulo del video: {estado.estrategia.titulo_ganador}

Guion a evaluar (por escenas):
{texto_escenas}"""

    resultado = generar_json(SYSTEM_PROMPT, user_prompt, temperatura=0.3)

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
        request.proyecto_id,
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


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
