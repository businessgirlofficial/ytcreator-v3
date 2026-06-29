"""
Agente 1.1 - Investigador de nicho
Depto 1 (Estrategia)

FASE 1 - IMPLEMENTACION REAL
================================
1. Busca en la web (DuckDuckGo, sin costo) que se esta publicando en
   el nicho dado: formatos, ganchos, angulos que estan funcionando.
2. Le pasa esos resultados a Groq (Llama 3.3 70B) para que sintetice
   patrones virales concretos, un tono de canal sugerido, y un
   "mood" que el Depto 4 (Audio) usara mas adelante para elegir musica.

Si la busqueda web falla (sin internet, rate limit), el agente NO se
cae: avisa a Groq que no hubo resultados y le pide que use su propio
conocimiento del nicho. Si GROQ_API_KEY no esta configurada, el
agente falla con un mensaje claro (lo captura la plantilla base).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES
from shared.groq_client import generar_json
from shared.knowledge_loader import inyectar_knowledge
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager
from shared.web_search import buscar

AGENTE_ID = "1.1_investigador"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Investigador de nicho y patrones virales")
state = StateManager()

SYSTEM_PROMPT = """Eres un estratega de contenido de YouTube especializado en analizar
nichos y detectar patrones virales reales y reusables. Trabajas en espanol.

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "patrones_virales": ["patron 1 concreto y accionable", "patron 2", "..."],
  "canal_tono": "descripcion corta del tono de canal recomendado (ej: educativo serio, entretenimiento rapido)",
  "mood": "una palabra o frase corta para el mood musical (ej: tenso, inspirador, urgente, calmado)"
}

Identifica entre 7 y 10 patrones virales. Cada patron debe ser ESPECIFICO y ACCIONABLE:
- Menciona elementos concretos: cifras, fechas, eventos, referencias culturales del nicho
- Describe la ESTRUCTURA exacta del gancho (ej: "abrir con una cifra de perdida economica en los primeros 5 segundos")
- Incluye ejemplos reales cuando sea posible (ej: "usar titulos tipo 'El Portal 888: lo que nadie te dice'")
- Describe tecnicas de engagement especificas (ej: "incluir un llamado a la accion en el minuto 5 invitando a explorar mas")

NUNCA des consejos genericos como "se mas creativo", "usa buenas miniaturas", "publica contenido de calidad".
Cada patron debe ser tan concreto que alguien pueda aplicarlo directamente en su proximo video."""


def _construir_contexto_busqueda(nicho: str) -> str:
    try:
        resultados = buscar(f"videos virales {nicho} youtube", max_resultados=8)
    except Exception as exc:  # la busqueda no es critica: degradamos, no fallamos
        return f"(busqueda web no disponible: {exc}; usa tu conocimiento general del nicho)"

    if not resultados:
        return "(la busqueda no devolvio resultados; usa tu conocimiento general del nicho)"

    return "\n".join(f"- {r['titulo']}: {r['resumen']}" for r in resultados)


def _construir_contexto_canal(proyecto_id: str) -> str:
    """Si el proyecto tiene canal_id, extrae contexto del canal para enriquecer el prompt."""
    try:
        estado = state.leer(proyecto_id)
        ctx = estado.estrategia.contexto_canal
        if not ctx:
            return ""

        partes = []
        if ctx.get("nicho_principal"):
            partes.append(f"Nicho del canal: {ctx['nicho_principal']}")
        if ctx.get("patrones_titulo_exitosos"):
            partes.append(f"Patrones de titulo que funcionan: {', '.join(ctx['patrones_titulo_exitosos'])}")
        if ctx.get("formatos_exitosos"):
            partes.append(f"Formatos exitosos: {', '.join(ctx['formatos_exitosos'])}")

        competidores = estado.estrategia.competidores_contexto or []
        if competidores:
            comp_lines = []
            for c in competidores[:3]:
                nombre = c.get("nombre", "?")
                tops = [v.get("titulo", "") for v in c.get("top_videos", [])[:3]]
                if tops:
                    comp_lines.append(f"  - {nombre}: {', '.join(tops)}")
            if comp_lines:
                partes.append(f"Videos virales de competidores:\n" + "\n".join(comp_lines))

        tendencias = estado.estrategia.tendencias_nicho or []
        if tendencias:
            partes.append(f"Tendencias del nicho: {', '.join(tendencias[:5])}")

        brechas = estado.estrategia.brechas_contenido or []
        if brechas:
            partes.append(f"Brechas de contenido: {', '.join(brechas[:5])}")

        return "\n".join(partes) if partes else ""
    except Exception:
        return ""


def logica(request: AgenteRequest) -> dict:
    nicho = request.parametros.get("nicho", "")
    if not nicho:
        raise ValueError("Falta el parametro 'nicho'")

    contexto = _construir_contexto_busqueda(nicho)
    contexto_canal = _construir_contexto_canal(request.proyecto_id)

    user_prompt = f"""Nicho a analizar: {nicho}

Resultados de busqueda reciente sobre este nicho en YouTube:
{contexto}"""

    if contexto_canal:
        user_prompt += f"""

Inteligencia del canal (datos reales de YouTube):
{contexto_canal}

Usa estos datos reales para fundamentar tus patrones virales. Prioriza
patrones que ya han demostrado funcionar en este canal y su competencia."""
    else:
        user_prompt += "\n\nSintetiza patrones virales concretos a partir de esto."

    user_prompt = inyectar_knowledge(user_prompt, "depto_1_estrategia")
    resultado = generar_json(SYSTEM_PROMPT, user_prompt)

    patrones_virales = resultado.get("patrones_virales", [])
    canal_tono = resultado.get("canal_tono")
    mood = resultado.get("mood")

    state.actualizar(
        request.proyecto_id,
        estrategia={
            "nicho": nicho,
            "patrones_virales": patrones_virales,
            "canal_tono": canal_tono,
            "mood": mood,
        },
    )
    return {
        "nicho": nicho,
        "patrones_virales": patrones_virales,
        "canal_tono": canal_tono,
        "mood": mood,
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
