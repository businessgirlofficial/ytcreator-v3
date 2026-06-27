"""
Agente 3.1 - Prompt maker
Depto 3 (Visual)

Aplica los 5 Candados de consistencia visual a cada escena del guion.

Los 5 candados se dividen en dos grupos:

  3 CANDADOS QUE SE MANTIENEN IDENTICOS en todo el video:
    1. Subject Lock      - descripcion exacta del sujeto/personaje
    2. Background Lock   - descripcion exacta del entorno
    3. Estilo fijo       - estilo de render (del catalogo de estilos SDXL)

  2 CANDADOS QUE VARIAN por escena (para evitar clonacion visual):
    4. Dinamismo de camara - tipo de plano distinto por escena
    5. Anti-clonacion      - un micro-detalle distinto por escena

Cuando el canal tiene Identidad Visual configurada, los 3 candados fijos
se DERIVAN de ella en lugar de generarse desde cero. El estilo se aplica
via el catalogo de estilos SDXL (prompt_template + negative_prompt).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.channel_manager import ChannelManager
from shared.config import REGISTRO_AGENTES
from shared.claude_client import revisar_con_claude
from shared.groq_client import generar_json
from shared.knowledge_loader import inyectar_knowledge
from shared.schemas import AgenteRequest, AgenteResponse, IdentidadVisualCanal
from shared.state_manager import StateManager
from shared.visual_styles import aplicar_estilo, aplicar_estilo_custom

AGENTE_ID = "3.1_prompt_maker"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Aplica los 5 Candados y genera prompts por escena")
state = StateManager()
channels = ChannelManager()

PLANOS_CAMARA_FALLBACK = [
    "wide shot", "medium shot", "close-up shot", "over-the-shoulder shot",
    "low angle shot", "high angle shot", "three-quarter shot",
]

SYSTEM_PROMPT_LOCKS = """Eres un director de fotografia especializado en generacion de
imagenes con IA (FLUX.1) para videos de YouTube.

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

SYSTEM_PROMPT_LOCKS_CON_IDENTIDAD = """Eres un director de fotografia especializado en generacion de
imagenes con IA (FLUX.1) para videos de YouTube.

El canal tiene una IDENTIDAD VISUAL establecida que DEBES respetar.
Tu trabajo es ADAPTAR estos elementos al tema del video actual,
manteniendolos coherentes con la identidad del canal.

Define 2 elementos (el estilo ya esta definido por el catalogo):

- subject_lock: descripcion fisica EXACTA del sujeto. Si el canal tiene
  un personaje principal definido, DEBES usarlo como base y solo adaptarlo
  al contexto del video actual. Si no tiene personaje, describe el tipo de
  elemento visual recurrente coherente con los elementos del canal.
- background_lock: descripcion del entorno/fondo coherente con el fondo base
  del canal, adaptado al tema del video actual.

SIEMPRE respondes en JSON valido, EN INGLES:
{
  "subject_lock": "...",
  "background_lock": "..."
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


def _obtener_identidad(canal_id: str | None) -> IdentidadVisualCanal | None:
    if not canal_id:
        return None
    try:
        canal = channels.leer(canal_id)
        if canal.identidad_visual.configurado:
            return canal.identidad_visual
    except FileNotFoundError:
        pass
    return None


def _generar_locks_sin_identidad(nicho: str, titulo: str, canal_tono: str | None) -> dict:
    user_prompt = f"""Nicho: {nicho}
Titulo del video: {titulo}
Tono de canal: {canal_tono or "no especificado"}"""
    user_prompt = inyectar_knowledge(user_prompt, "depto_3_visual")
    return generar_json(SYSTEM_PROMPT_LOCKS, user_prompt, temperatura=0.7)


def _generar_locks_con_identidad(
    nicho: str, titulo: str, identidad: IdentidadVisualCanal
) -> dict:
    constraints = []
    if identidad.personaje_principal:
        constraints.append(f"Personaje principal del canal: {identidad.personaje_principal}")
    if identidad.fondo_base:
        constraints.append(f"Entorno base del canal: {identidad.fondo_base}")
    if identidad.elementos_recurrentes:
        constraints.append(f"Elementos recurrentes: {', '.join(identidad.elementos_recurrentes)}")
    if identidad.paleta_colores:
        constraints.append(f"Paleta de colores: {identidad.paleta_colores}")
    if identidad.iluminacion:
        constraints.append(f"Iluminacion: {identidad.iluminacion}")

    user_prompt = f"""Nicho: {nicho}
Titulo del video: {titulo}

IDENTIDAD VISUAL DEL CANAL (respetar como base):
{chr(10).join(f'- {c}' for c in constraints)}

Adapta el subject y background al tema de ESTE video, pero manteniendolos
coherentes con la identidad del canal."""

    return generar_json(SYSTEM_PROMPT_LOCKS_CON_IDENTIDAD, user_prompt, temperatura=0.7)


def _generar_variaciones(escenas: list[dict]) -> list[dict]:
    listado = "\n".join(f"{e['numero']}. [{e['tipo'].upper()}] {e['texto']}" for e in escenas)
    resultado = generar_json(SYSTEM_PROMPT_VARIACION, listado, temperatura=0.9)
    return resultado.get("variaciones", [])


def _aplicar_anticlonacion(escenas: list[dict], variaciones: list[dict]) -> list[dict]:
    """Candado 5 forzado en codigo: dos escenas consecutivas nunca
    comparten el mismo plano de camara."""
    por_numero = {v.get("numero"): v for v in variaciones}
    resultado = []
    plano_anterior = None
    indice_fallback = 0

    for escena in escenas:
        v = por_numero.get(escena["numero"], {})
        plano = v.get("camera_shot") or ""
        micro = v.get("micro_variacion") or "natural moment, candid framing"

        if not plano or plano == plano_anterior:
            for _intento in range(len(PLANOS_CAMARA_FALLBACK)):
                candidato = PLANOS_CAMARA_FALLBACK[indice_fallback % len(PLANOS_CAMARA_FALLBACK)]
                indice_fallback += 1
                if candidato != plano_anterior:
                    plano = candidato
                    break
            else:
                plano = candidato

        resultado.append({"numero": escena["numero"], "camera_shot": plano, "micro_variacion": micro})
        plano_anterior = plano

    return resultado


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    estrategia = estado.estrategia
    escenas = [e.model_dump() for e in estado.guion.escenas]

    if not escenas:
        raise ValueError("No hay escenas en el guion: corre primero el Depto 2 (Guion)")

    canal_id = estrategia.canal_id or estado.canal_id
    identidad = _obtener_identidad(canal_id)

    override_slug = request.parametros.get("override_estilo")

    if identidad:
        locks = _generar_locks_con_identidad(
            estrategia.nicho, estrategia.titulo_ganador or "", identidad
        )
        estilo_slug = override_slug or identidad.estilo_slug
        estilo_template = identidad.prompt_template
        estilo_negative = identidad.negative_prompt
    else:
        locks = _generar_locks_sin_identidad(
            estrategia.nicho, estrategia.titulo_ganador or "", estrategia.canal_tono
        )
        estilo_slug = override_slug or "cinematic"
        estilo_template = ""
        estilo_negative = ""

    locks = revisar_con_claude(locks, f"""Revisa estos candados de consistencia visual para un video de YouTube.
Titulo: {estrategia.titulo_ganador or ""}
Nicho: {estrategia.nicho}

Verifica y mejora si es necesario:
1. subject_lock: descripcion fisica EXACTA y detallada, consistente para todas las escenas
2. background_lock: entorno coherente y visualmente atractivo
{"3. estilo_fijo: estilo de render completo (iluminacion, paleta, lente)" if not identidad else ""}
4. Todo en ingles (sirve como prompt de generacion de imagenes FLUX.1)

Si algo es vago, generico o inconsistente, corrigelo con mas detalle.
Devuelve el JSON con las mismas claves.""")

    variaciones_raw = _generar_variaciones(escenas)
    variaciones = _aplicar_anticlonacion(escenas, variaciones_raw)
    variaciones_por_numero = {v["numero"]: v for v in variaciones}

    subject_lock = locks.get("subject_lock", "")
    background_lock = locks.get("background_lock", "")

    if identidad:
        estilo_fijo = ""
    else:
        estilo_fijo = locks.get("estilo_fijo", "")

    for escena in escenas:
        v = variaciones_por_numero.get(escena["numero"], {})
        prompt_base = ", ".join(
            filter(None, [
                subject_lock,
                background_lock,
                estilo_fijo,
                v.get("camera_shot"),
                v.get("micro_variacion"),
            ])
        )

        if estilo_template:
            prompt_final, negative = aplicar_estilo_custom(
                estilo_template, estilo_negative, prompt_base
            )
        else:
            prompt_final, negative = aplicar_estilo(estilo_slug, prompt_base)

        escena["prompt_visual"] = prompt_final
        escena["negative_prompt"] = negative

    candados_aplicados = {
        "subject_lock": subject_lock,
        "background_lock": background_lock,
        "estilo_fijo": estilo_fijo or f"[catalogo:{estilo_slug}]",
    }

    state.actualizar(
        request.proyecto_id,
        guion={"escenas": escenas},
        visual={
            "prompts_generados": True,
            "candados_aplicados": candados_aplicados,
            "estilo_aplicado": estilo_slug,
        },
    )
    return {
        "escenas_con_prompt": len(escenas),
        "candados_aplicados": candados_aplicados,
        "estilo_aplicado": estilo_slug,
        "identidad_canal_usada": identidad is not None,
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
