"""
Agente 2.1 - Guionista
Depto 2 (Guion)

FASE 2 - IMPLEMENTACION REAL
================================
Escribe el guion completo con Groq, dividido en escenas numeradas:
  - Hook (1-2 escenas, siempre las primeras)
  - Cuerpo (al menos 5 escenas, una por cada punto/elemento viral)
  - CTA (1 escena, siempre la ultima)

Si el Evaluador (2.2) rechazo un intento anterior, este agente NO
genera desde cero: toma el guion previo + el feedback especifico y
le pide a Groq que reescriba atacando ese feedback puntual. Esto es
lo que hace que el loop de reescritura del orquestador central
(ya construido en la Fase 0) realmente mejore el guion en cada
vuelta, en vez de tirar los dados de nuevo cada vez.

La asignacion de que escenas usan video IA real (primeras 12, segun
la estrategia hibrida ya decidida al inicio del proyecto) se hace
aqui en codigo, no se le deja al LLM.
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

AGENTE_ID = "2.1_guionista"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Escribe el guion completo con estructura viral")
state = StateManager()

ESCENAS_CON_VIDEO_IA = 12  # estrategia hibrida ya decidida: primeras N con video real

SYSTEM_PROMPT = """Eres un guionista viral especializado en YouTube. Escribes en espanol,
con frases cortas y ritmo hablado (este texto se convierte directo en
audio narrado, no es para leer en pantalla).

Estructura SIEMPRE el guion en 3 partes:
- Hook: 1 o 2 escenas como maximo, las primeras. Debe generar tension
  o curiosidad inmediata en los primeros 15-30 segundos.
- Cuerpo: AL MENOS 5 escenas, una por cada punto o elemento viral
  desarrollado. Cada escena de cuerpo debe cerrar con un micro-gancho
  hacia la siguiente.
- CTA: exactamente 1 escena, siempre la ultima, con una accion clara
  y especifica (suscribirse, comentar algo concreto, ver otro video).

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "escenas": [
    {"texto": "...", "tipo": "hook"},
    {"texto": "...", "tipo": "cuerpo"},
    ...
    {"texto": "...", "tipo": "cta"}
  ]
}

Cada "texto" debe ser de 2 a 4 frases, listo para narrar en voz alta.
No incluyas numeracion, eso lo maneja el sistema."""


def _normalizar_escenas(escenas_raw: list[dict]) -> list[dict]:
    """Renumera secuencialmente, sanea el tipo y asigna usa_video_ia en codigo
    (nunca confiamos en que el LLM numere bien o respete el enum de tipos)."""
    escenas = []
    contador = 0
    for e in escenas_raw:
        texto = (e.get("texto") or "").strip()
        if not texto:
            continue
        contador += 1
        tipo = e.get("tipo", "cuerpo")
        if tipo not in ("hook", "cuerpo", "cta"):
            tipo = "cuerpo"
        escenas.append(
            {
                "numero": contador,
                "texto": texto,
                "tipo": tipo,
                "usa_video_ia": contador <= ESCENAS_CON_VIDEO_IA,
            }
        )
    return escenas


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    estrategia = estado.estrategia
    guion_previo = estado.guion

    if not estrategia.titulo_ganador:
        raise ValueError("No hay titulo_ganador en el estado: corre primero el Depto 1 (Estrategia)")

    contexto_estrategia = f"""Nicho: {estrategia.nicho}
Titulo del video: {estrategia.titulo_ganador}
Tono de canal: {estrategia.canal_tono or "no especificado"}
Patrones virales detectados: {", ".join(estrategia.patrones_virales) or "ninguno"}"""

    ctx = estrategia.contexto_canal
    if ctx:
        if ctx.get("audiencia_objetivo"):
            contexto_estrategia += f"\nAudiencia objetivo: {ctx['audiencia_objetivo']}"
        if ctx.get("formatos_exitosos"):
            contexto_estrategia += f"\nFormatos que funcionan en el canal: {', '.join(ctx['formatos_exitosos'])}"
        if ctx.get("tono"):
            contexto_estrategia += f"\nEstilo de comunicacion del canal: {ctx['tono']}"

    es_reescritura = bool(guion_previo.feedback_evaluador) and not guion_previo.aprobado

    if es_reescritura:
        user_prompt = f"""{contexto_estrategia}

Este es tu intento numero {guion_previo.intentos_reescritura + 1}.

Tu guion anterior fue RECHAZADO por el evaluador con este feedback especifico:
"{guion_previo.feedback_evaluador}"

Guion anterior (para que no repitas los mismos errores):
{guion_previo.texto_completo}

Reescribe el guion completo atacando DIRECTAMENTE el feedback de arriba.
No cambies lo que ya funcionaba si el feedback no lo menciono."""
    else:
        user_prompt = f"""{contexto_estrategia}

Escribe el guion completo desde cero."""

    resultado = generar_json(SYSTEM_PROMPT, user_prompt, temperatura=0.9 if es_reescritura else 0.8)
    escenas_raw = resultado.get("escenas", [])
    if not escenas_raw:
        raise ValueError("Groq no devolvio escenas en el formato esperado")

    escenas = _normalizar_escenas(escenas_raw)
    if not escenas:
        raise ValueError("Todas las escenas devueltas estaban vacias tras normalizar")

    texto_completo = "\n\n".join(e["texto"] for e in escenas)

    state.actualizar(
        request.proyecto_id,
        guion={
            "texto_completo": texto_completo,
            "escenas": escenas,
            "aprobado": False,  # el Evaluador (2.2) decide esto, no este agente
        },
    )
    return {"num_escenas": len(escenas), "es_reescritura": es_reescritura}


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
