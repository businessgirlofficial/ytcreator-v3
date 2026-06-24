"""
Agente 1.3 - Director de arte
Depto 1 (Estrategia)

FASE 1 - IMPLEMENTACION REAL
================================
Toma el titulo ganador del Copywriter (1.2) y le pide a Groq que
diseñe la composicion completa de la miniatura: fondo, texto overlay
corto, posicion, paleta de color y el elemento focal. Con eso arma
el prompt de imagen final, listo para que el Agente 3.2 (Generador
Visual) lo use mas adelante en Kaggle con Juggernaut XL.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.channel_manager import ChannelManager
from shared.config import REGISTRO_AGENTES
from shared.groq_client import generar_json
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "1.3_director_arte"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Disena el concepto y prompt de la miniatura")
state = StateManager()
channels = ChannelManager()

SYSTEM_PROMPT = """Eres un director de arte especializado en miniaturas (thumbnails)
de YouTube de alto CTR. Trabajas en espanol salvo el prompt de imagen final.

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "fondo": "descripcion visual concreta del fondo o escena",
  "texto_principal": "version corta del titulo para overlay, maximo 5 palabras, en mayusculas",
  "posicion_texto": "izquierda, derecha o centro",
  "paleta": "2-3 colores dominantes y por que generan contraste/atencion",
  "elemento_focal": "que objeto, persona o expresion debe ser el punto focal",
  "prompt_imagen": "prompt completo EN INGLES, listo para un generador de imagenes (estilo, iluminacion, composicion), sin incluir el texto superpuesto"
}"""


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    titulo = estado.estrategia.titulo_ganador
    nicho = estado.estrategia.nicho

    if not titulo:
        raise ValueError("No hay titulo_ganador en el estado: corre primero el Agente 1.2 (Copywriter)")

    user_prompt = f"""Nicho: {nicho}
Titulo ganador: {titulo}"""

    ctx = estado.estrategia.contexto_canal
    if ctx and ctx.get("estilo_visual"):
        user_prompt += f"""

Estilo visual establecido del canal: {ctx['estilo_visual']}
Mantén coherencia con este estilo pero hazlo atractivo para el tema actual."""

    # Performance feedback: CTR de miniaturas anteriores
    canal_id = estado.estrategia.canal_id or estado.canal_id
    if canal_id:
        try:
            canal = channels.leer(canal_id)
            if canal.patrones_exitosos:
                alto_ctr = [p for p in canal.patrones_exitosos[-5:] if p.get("ctr")]
                if alto_ctr:
                    user_prompt += f"""

Miniaturas con ALTO CTR en videos anteriores (referencia de estilo que funciona):
{chr(10).join(f'- "{p.get("titulo", "?")}" → CTR {p.get("ctr")}%' for p in alto_ctr)}
Intenta capturar elementos visuales similares al estilo que genera alto CTR."""

            if canal.patrones_a_evitar:
                bajo_ctr = [p for p in canal.patrones_a_evitar[-3:] if p.get("ctr")]
                if bajo_ctr:
                    user_prompt += f"""

Miniaturas con BAJO CTR (evita este estilo):
{chr(10).join(f'- "{p.get("titulo", "?")}" → CTR {p.get("ctr")}%' for p in bajo_ctr)}"""
        except FileNotFoundError:
            pass

    user_prompt += "\n\nDisena la miniatura para este video."

    resultado = generar_json(SYSTEM_PROMPT, user_prompt)

    miniatura_composicion = {
        "fondo": resultado.get("fondo"),
        "texto_principal": resultado.get("texto_principal"),
        "posicion_texto": resultado.get("posicion_texto"),
        "paleta": resultado.get("paleta"),
        "elemento_focal": resultado.get("elemento_focal"),
    }
    miniatura_prompt = resultado.get("prompt_imagen", "")

    state.actualizar(
        request.proyecto_id,
        estrategia={
            "miniatura_prompt": miniatura_prompt,
            "miniatura_composicion": miniatura_composicion,
        },
    )
    return {"miniatura_prompt": miniatura_prompt, "miniatura_composicion": miniatura_composicion}


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
