"""
Agente 3.1 - Prompt maker
Depto 3 (Visual)

FASE 3 - IMPLEMENTACION REAL
================================
Aplica los 5 Candados de consistencia visual a cada escena del guion.

NOTA HONESTA: no tengo acceso al codigo original de tu notebook v7,
asi que esta es MI interpretacion de como deben funcionar los 5
Candados a partir de lo que discutimos (Subject Lock, Background
Lock, Anti-clonacion, Dinamismo de camara, Estilo fijo). Si tu
definicion original tiene matices distintos, dimelo y la ajusto.

Mi interpretacion separa los 5 candados en dos grupos:

  3 CANDADOS QUE SE MANTIENEN IDENTICOS en todo el video (Groq los
  genera UNA sola vez, el codigo los pega literalmente en cada
  escena, nunca se le pide a Groq que los regenere por escena):
    1. Subject Lock      - descripcion exacta del sujeto/personaje
    2. Background Lock   - descripcion exacta del entorno
    3. Estilo fijo         - estilo de render, iluminacion, paleta

  2 CANDADOS QUE VARIAN A PROPOSITO escena por escena (para que el
  video no se vea como la misma imagen clonada N veces):
    4. Dinamismo de camara - tipo de plano distinto por escena
    5. Anti-clonacion       - un micro-detalle distinto por escena

El candado 5 (anti-clonacion) se fuerza en CODIGO ademas de pedirselo
a Groq: si dos escenas consecutivas terminan con el mismo plano de
camara, el codigo lo reemplaza por el siguiente de una lista fija,
sin importar lo que haya devuelto el LLM.
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

AGENTE_ID = "3.1_prompt_maker"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Aplica los 5 Candados y genera prompts por escena")
state = StateManager()

# Candado 5 (anti-clonacion): catalogo fijo para garantizar variedad
# determinista si Groq repite el mismo plano en escenas vecinas.
PLANOS_CAMARA_FALLBACK = [
    "wide shot", "medium shot", "close-up shot", "over-the-shoulder shot",
    "low angle shot", "high angle shot", "three-quarter shot",
]

SYSTEM_PROMPT_LOCKS = """Eres un director de fotografia especializado en generacion de
imagenes con IA (Stable Diffusion / Juggernaut XL) para videos de YouTube.

Define 3 elementos que se repetiran IDENTICOS en cada escena del
video, para garantizar consistencia visual:

- subject_lock: descripcion fisica EXACTA y detallada del sujeto o
  personaje principal. Si el video no tiene un personaje fijo (es
  solo b-roll conceptual), describe en su lugar el tipo de elemento
  visual recurrente.
- background_lock: descripcion del entorno/fondo que se mantiene
  coherente en todo el video.
- estilo_fijo: el estilo de renderizado completo (tipo de fotografia,
  iluminacion general, paleta de color, lente, grano de imagen).

SIEMPRE respondes en JSON valido, EN INGLES (sirve como prompt de
generacion de imagenes):
{
  "subject_lock": "...",
  "background_lock": "...",
  "estilo_fijo": "..."
}"""

SYSTEM_PROMPT_VARIACION = """Eres un director de fotografia. Te paso una lista de escenas
de un guion de YouTube. Para cada escena define DOS cosas que deben
ser DIFERENTES de las escenas vecinas, para que el video no se vea
como la misma imagen repetida:

- camera_shot: tipo de plano/angulo (ej: wide shot, medium shot,
  close-up, over-the-shoulder shot, low angle shot, high angle shot)
- micro_variacion: un detalle pequeno que cambia (pose, gesto,
  iluminacion del momento, prop en escena) sin romper la consistencia
  del sujeto ni del fondo.

SIEMPRE respondes en JSON valido, EN INGLES:
{
  "variaciones": [
    {"numero": 1, "camera_shot": "...", "micro_variacion": "..."},
    ...
  ]
}
Debes devolver EXACTAMENTE una entrada por cada escena, en el mismo orden."""


def _generar_locks(nicho: str, titulo: str, canal_tono: str | None) -> dict:
    user_prompt = f"""Nicho: {nicho}
Titulo del video: {titulo}
Tono de canal: {canal_tono or "no especificado"}"""
    return generar_json(SYSTEM_PROMPT_LOCKS, user_prompt, temperatura=0.7)


def _generar_variaciones(escenas: list[dict]) -> list[dict]:
    listado = "\n".join(f"{e['numero']}. [{e['tipo'].upper()}] {e['texto']}" for e in escenas)
    resultado = generar_json(SYSTEM_PROMPT_VARIACION, listado, temperatura=0.9)
    return resultado.get("variaciones", [])


def _aplicar_anticlonacion(escenas: list[dict], variaciones: list[dict]) -> list[dict]:
    """Candado 5 forzado en codigo: dos escenas consecutivas nunca
    comparten el mismo plano de camara, sin importar lo que devolvio Groq."""
    por_numero = {v.get("numero"): v for v in variaciones}
    resultado = []
    plano_anterior = None
    indice_fallback = 0

    for escena in escenas:
        v = por_numero.get(escena["numero"], {})
        plano = v.get("camera_shot") or ""
        micro = v.get("micro_variacion") or "natural moment, candid framing"

        if not plano or plano == plano_anterior:
            # Busca el siguiente fallback que sea REALMENTE distinto al
            # plano anterior (no basta con tomar el primero de la lista:
            # si justo coincide con plano_anterior, seguimos buscando).
            for intento in range(len(PLANOS_CAMARA_FALLBACK)):
                candidato = PLANOS_CAMARA_FALLBACK[indice_fallback % len(PLANOS_CAMARA_FALLBACK)]
                indice_fallback += 1
                if candidato != plano_anterior:
                    plano = candidato
                    break
            else:
                plano = candidato  # caso extremo: nos quedamos con el ultimo probado

        resultado.append({"numero": escena["numero"], "camera_shot": plano, "micro_variacion": micro})
        plano_anterior = plano

    return resultado


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    estrategia = estado.estrategia
    escenas = [e.model_dump() for e in estado.guion.escenas]

    if not escenas:
        raise ValueError("No hay escenas en el guion: corre primero el Depto 2 (Guion)")

    locks = _generar_locks(estrategia.nicho, estrategia.titulo_ganador or "", estrategia.canal_tono)
    variaciones_raw = _generar_variaciones(escenas)
    variaciones = _aplicar_anticlonacion(escenas, variaciones_raw)
    variaciones_por_numero = {v["numero"]: v for v in variaciones}

    subject_lock = locks.get("subject_lock", "")
    background_lock = locks.get("background_lock", "")
    estilo_fijo = locks.get("estilo_fijo", "")

    for escena in escenas:
        v = variaciones_por_numero.get(escena["numero"], {})
        escena["prompt_visual"] = ", ".join(
            filter(None, [estilo_fijo, subject_lock, background_lock, v.get("camera_shot"), v.get("micro_variacion")])
        )

    candados_aplicados = {
        "subject_lock": subject_lock,
        "background_lock": background_lock,
        "estilo_fijo": estilo_fijo,
    }

    state.actualizar(
        request.proyecto_id,
        guion={"escenas": escenas},
        visual={"prompts_generados": True, "candados_aplicados": candados_aplicados},
    )
    return {"escenas_con_prompt": len(escenas), "candados_aplicados": candados_aplicados}


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
