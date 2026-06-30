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
from shared.channel_manager import ChannelManager
from shared.config import REGISTRO_AGENTES
from shared.claude_client import generar_json_claude
from shared.knowledge_loader import inyectar_knowledge
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager

AGENTE_ID = "1.2_copywriter"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Genera y valida titulos virales")
state = StateManager()
channels = ChannelManager()

LONGITUD_MIN_IDEAL = 40
LONGITUD_MAX_IDEAL = 70

SYSTEM_PROMPT_LIBRE = """Eres un copywriter viral especializado en titulos de YouTube en espanol.
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

SYSTEM_PROMPT_DIRIGIDO = """Eres un copywriter viral especializado en titulos de YouTube en espanol.
Se te proporciona un TITULO BASE de un cronograma de contenido. Tu trabajo
NO es generar titulos desde cero, sino REFINAR ese titulo base con 5 variaciones.

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "titulo_base_evaluacion": "breve evaluacion del titulo base (1 frase: que tiene de bueno y que se puede mejorar)",
  "titulos": [
    {"texto": "el titulo base original tal cual, si sigue siendo bueno", "framework": "original", "score_creativo": 0-100, "variacion": "original"},
    {"texto": "mismo tema, angulo ajustado por tendencia actual", "framework": "...", "score_creativo": 0-100, "variacion": "tendencia"},
    {"texto": "mismo tema, hook diferente", "framework": "...", "score_creativo": 0-100, "variacion": "hook"},
    {"texto": "mismo tema, formato pregunta o afirmacion (el opuesto al base)", "framework": "...", "score_creativo": 0-100, "variacion": "formato"},
    {"texto": "variacion mas agresiva/clickbait si los datos lo sugieren", "framework": "...", "score_creativo": 0-100, "variacion": "agresiva"}
  ]
}

Las 5 variaciones DEBEN mantener la ESENCIA del titulo base (mismo tema, misma promesa).
No reinventar el video — refinar el empaque.
Cada titulo debe tener idealmente entre 40 y 70 caracteres."""


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


def _construir_contexto_performance(canal_id: str | None) -> str:
    if not canal_id:
        return ""
    partes = []
    try:
        canal = channels.leer(canal_id)
        if canal.patrones_exitosos:
            exitosos = [
                f"- \"{p.get('titulo', '?')}\" (CTR {p.get('ctr', '?')}%)"
                for p in canal.patrones_exitosos[-5:] if p.get("ctr")
            ]
            if exitosos:
                partes.append(
                    "Titulos con ALTO CTR (REPLICA el estilo):\n"
                    + chr(10).join(exitosos)
                )
        if canal.patrones_a_evitar:
            evitar = [
                f"- \"{p.get('titulo', '?')}\" (CTR {p.get('ctr', '?')}%)"
                for p in canal.patrones_a_evitar[-3:] if p.get("ctr")
            ]
            if evitar:
                partes.append(
                    "Titulos con BAJO CTR (EVITA este estilo):\n"
                    + chr(10).join(evitar)
                )
    except FileNotFoundError:
        pass
    return "\n\n".join(partes)


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    nicho = estado.estrategia.nicho
    patrones = estado.estrategia.patrones_virales
    entrada_cron = request.parametros.get("entrada_cronograma")

    if not nicho:
        raise ValueError("No hay nicho en el estado: corre primero el Agente 1.1 (Investigador)")

    canal_id = estado.estrategia.canal_id or estado.canal_id
    ctx_performance = _construir_contexto_performance(canal_id)

    if entrada_cron:
        # ── MODO DIRIGIDO: refinar titulo base del cronograma ──
        titulo_base = request.parametros.get(
            "titulo_base_cronograma",
            entrada_cron.get("titulo_sugerido", ""),
        )
        angulo = request.parametros.get(
            "angulo_cronograma",
            entrada_cron.get("angulo", ""),
        )
        formato = request.parametros.get(
            "formato_cronograma",
            entrada_cron.get("formato", ""),
        )
        keywords = request.parametros.get(
            "keywords_cronograma",
            entrada_cron.get("keywords_recomendadas", []),
        )

        patrones_texto = "\n".join(f"- {p}" for p in patrones) if patrones else "(ninguno)"

        user_prompt = f"""MODO DIRIGIDO — Refinar titulo base del cronograma.

TITULO BASE A REFINAR: "{titulo_base}"
TEMA: {entrada_cron.get('tema', nicho)}
ANGULO: {angulo}
FORMATO DEL VIDEO: {formato}
KEYWORDS PLANEADAS: {', '.join(keywords) if keywords else 'N/A'}
NICHO: {nicho}

Patrones virales detectados:
{patrones_texto}"""

        ctx = estado.estrategia.contexto_canal
        if ctx and ctx.get("patrones_titulo_exitosos"):
            user_prompt += f"""

Formulas de titulo probadas del canal:
{chr(10).join(f'- {p}' for p in ctx['patrones_titulo_exitosos'])}"""

        if ctx_performance:
            user_prompt += f"\n\n{ctx_performance}"

        user_prompt += f"""

Genera exactamente 5 variaciones del titulo base. La primera DEBE ser
el titulo original tal cual. Las otras 4 son refinamientos que mantienen
la misma esencia pero con diferentes enfoques de copywriting.
Incorpora las keywords '{', '.join(keywords)}' de forma natural."""

        user_prompt = inyectar_knowledge(user_prompt, "depto_1_estrategia")
        resultado = generar_json_claude(SYSTEM_PROMPT_DIRIGIDO, user_prompt)

        titulos_raw = resultado.get("titulos", [])
        if not titulos_raw:
            raise ValueError("Claude no devolvio titulos en el formato esperado")

        validados = _validar_y_puntuar(titulos_raw)
        if not validados:
            raise ValueError("Ningun titulo paso la validacion")

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
            "modo": "dirigido",
            "titulo_base_cronograma": titulo_base,
            "titulo_base_evaluacion": resultado.get("titulo_base_evaluacion", ""),
            "titulos_validados": validados,
            "titulo_ganador": titulo_ganador,
            "titulo_subcampeon": titulo_subcampeon,
        }

    else:
        # ── MODO LIBRE: generar 10 titulos desde cero (comportamiento original) ──
        patrones_texto = "\n".join(f"- {p}" for p in patrones) if patrones else "(ninguno detectado)"
        user_prompt = f"""Nicho: {nicho}

Patrones virales detectados para este nicho:
{patrones_texto}"""

        ctx = estado.estrategia.contexto_canal
        if ctx and ctx.get("patrones_titulo_exitosos"):
            user_prompt += f"""

Formulas de titulo que ya funcionan en este canal y su competencia:
{chr(10).join(f'- {p}' for p in ctx['patrones_titulo_exitosos'])}

Usa estas formulas como referencia para generar titulos que encajen con
el estilo probado del canal, pero con variaciones frescas."""

        if ctx_performance:
            user_prompt += f"\n\n{ctx_performance}"

        user_prompt += "\n\nGenera 10 titulos usando frameworks distintos."

        user_prompt = inyectar_knowledge(user_prompt, "depto_1_estrategia")
        resultado = generar_json_claude(SYSTEM_PROMPT_LIBRE, user_prompt)
        titulos_raw = resultado.get("titulos", [])
        if not titulos_raw:
            raise ValueError("Claude no devolvio titulos en el formato esperado")

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
            "modo": "libre",
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
