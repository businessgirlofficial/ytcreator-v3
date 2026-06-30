"""
Agente 1.3 - Director de arte
Depto 1 (Estrategia)

Toma el titulo ganador del Copywriter (1.2) y diseña la composicion
completa de la miniatura: fondo, texto overlay, paleta, elemento focal
y el prompt de imagen final para Juggernaut XL.

Cuando el canal tiene Identidad Visual configurada, la miniatura
respeta la paleta, personaje y estilo del canal.
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
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager
from shared.visual_styles import aplicar_estilo, aplicar_estilo_custom

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

SYSTEM_PROMPT_CON_IDENTIDAD = """Eres un director de arte especializado en miniaturas (thumbnails)
de YouTube de alto CTR. Trabajas en espanol salvo el prompt de imagen final.

El canal tiene una IDENTIDAD VISUAL que DEBES respetar en la miniatura:
{constraints}

SIEMPRE respondes en JSON valido con este formato exacto:
{{
  "fondo": "descripcion visual concreta del fondo, coherente con el entorno del canal",
  "texto_principal": "version corta del titulo para overlay, maximo 5 palabras, en mayusculas",
  "posicion_texto": "izquierda, derecha o centro",
  "paleta": "DEBE usar la paleta del canal. Explica como se aplica para este video",
  "elemento_focal": "que objeto, persona o expresion debe ser el punto focal (usar personaje del canal si tiene)",
  "prompt_imagen": "prompt completo EN INGLES, coherente con el estilo visual del canal, sin incluir el texto superpuesto"
}}"""


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)
    titulo = estado.estrategia.titulo_ganador
    nicho = estado.estrategia.nicho

    if not titulo:
        raise ValueError("No hay titulo_ganador en el estado: corre primero el Agente 1.2 (Copywriter)")

    canal_id = estado.estrategia.canal_id or estado.canal_id
    identidad = None
    if canal_id:
        try:
            canal = channels.leer(canal_id)
            if canal.identidad_visual.configurado:
                identidad = canal.identidad_visual
        except FileNotFoundError:
            pass

    entrada_cron = request.parametros.get("entrada_cronograma")
    tipo_contenido_cron = request.parametros.get("tipo_contenido_cronograma", "")
    formato_cron = request.parametros.get("formato_cronograma", "")
    datos_soporte_cron = request.parametros.get("datos_soporte_cronograma", {})

    user_prompt = f"""Nicho: {nicho}
Titulo ganador: {titulo}"""

    if entrada_cron:
        user_prompt += f"""

CONTEXTO DEL CRONOGRAMA (modo dirigido):
Tipo de contenido: {tipo_contenido_cron or entrada_cron.get('tipo_contenido', '')}
Formato del video: {formato_cron or entrada_cron.get('formato', '')}
Angulo: {entrada_cron.get('angulo', '')}"""

        if datos_soporte_cron:
            comp_ref = datos_soporte_cron.get("competidor_referencia", "")
            if comp_ref:
                user_prompt += f"\nCompetidor de referencia: {comp_ref} (diferenciarse visualmente)"
            fuente = datos_soporte_cron.get("fuente", "")
            if fuente:
                user_prompt += f"\nFuente de la idea: {fuente}"

        tipo_guias = {
            "trending": "Usa colores URGENTES (rojo, amarillo). Expresiones de sorpresa/impacto. Sensacion de novedad.",
            "brecha": "Tono EXCLUSIVO, como si revelaras un secreto. Contraste fuerte. Elemento de misterio.",
            "evergreen": "Tono PROFESIONAL y limpio. Claridad visual. Que se vea atemporal, no efimero.",
            "follow_up": "Conectar visualmente con el video anterior. Usar 'Parte 2' o continuidad visual.",
            "serie": "Mantener formato visual consistente con otros videos de la serie. Numeracion visible.",
            "viral_reaccion": "Expresion facial exagerada. Colores llamativos. Elemento de sorpresa visual.",
        }
        tipo_key = tipo_contenido_cron or entrada_cron.get("tipo_contenido", "")
        if tipo_key in tipo_guias:
            user_prompt += f"\n\nGUIA VISUAL POR TIPO ({tipo_key}): {tipo_guias[tipo_key]}"

    if identidad:
        constraints = []
        if identidad.personaje_principal:
            constraints.append(f"- Personaje principal: {identidad.personaje_principal}")
            if identidad.personaje_nombre:
                constraints.append(f"  (nombre: {identidad.personaje_nombre})")
        if identidad.paleta_colores:
            constraints.append(f"- Paleta de colores del canal: {identidad.paleta_colores}")
        if identidad.fondo_base:
            constraints.append(f"- Entorno base: {identidad.fondo_base}")
        if identidad.elementos_recurrentes:
            constraints.append(f"- Elementos recurrentes: {', '.join(identidad.elementos_recurrentes)}")
        if identidad.iluminacion:
            constraints.append(f"- Iluminacion: {identidad.iluminacion}")

        system_prompt = SYSTEM_PROMPT_CON_IDENTIDAD.format(
            constraints=chr(10).join(constraints)
        )
    else:
        system_prompt = SYSTEM_PROMPT
        ctx = estado.estrategia.contexto_canal
        if ctx and ctx.get("estilo_visual"):
            user_prompt += f"""

Estilo visual establecido del canal: {ctx['estilo_visual']}
Mantén coherencia con este estilo pero hazlo atractivo para el tema actual."""

    if canal_id:
        try:
            canal_data = channels.leer(canal_id)

            # ── Patrones visuales REALES de miniaturas exitosas ──
            patron_mini = canal_data.patrones_miniatura_exitosos
            if patron_mini and patron_mini.total_videos_analizados > 0:
                user_prompt += f"""

=== PATRONES VISUALES REALES DE MINIATURAS EXITOSAS (basado en {patron_mini.total_videos_analizados} miniaturas analizadas) ===
Colores dominantes en el nicho: {', '.join(patron_mini.colores_frecuentes) if patron_mini.colores_frecuentes else 'N/A'}
Uso de texto overlay: {patron_mini.usa_texto_overlay_pct}% de las miniaturas exitosas lo usan
Uso de rostros: {patron_mini.usa_rostro_pct}% de las miniaturas exitosas lo usan
Expresiones faciales comunes: {', '.join(patron_mini.expresiones_comunes) if patron_mini.expresiones_comunes else 'N/A'}
Composiciones que funcionan: {', '.join(patron_mini.composiciones_comunes[:3]) if patron_mini.composiciones_comunes else 'N/A'}
Elementos graficos frecuentes: {', '.join(patron_mini.elementos_frecuentes) if patron_mini.elementos_frecuentes else 'N/A'}
Estilos visuales comunes: {', '.join(patron_mini.estilos_comunes[:3]) if patron_mini.estilos_comunes else 'N/A'}
Resumen: {patron_mini.resumen}

USA estos patrones como BASE para tu diseno. Las miniaturas exitosas del nicho
siguen estos patrones — tu miniatura debe seguirlos pero con la identidad propia del canal.
==="""

            patron_evitar = canal_data.patrones_miniatura_evitar
            if patron_evitar and patron_evitar.total_videos_analizados > 0:
                user_prompt += f"""

PATRONES DE MINIATURA A EVITAR ({patron_evitar.total_videos_analizados} miniaturas con bajo CTR):
Colores: {', '.join(patron_evitar.colores_frecuentes[:3]) if patron_evitar.colores_frecuentes else 'N/A'}
Estilos: {', '.join(patron_evitar.estilos_comunes[:2]) if patron_evitar.estilos_comunes else 'N/A'}
Resumen: {patron_evitar.resumen}
EVITA estos patrones visuales."""

            # ── Analisis de miniaturas individuales de competidores top ──
            analisis_individuales = []
            for comp in canal_data.competidores[:3]:
                for v in comp.top_videos[:2]:
                    if v.analisis_miniatura:
                        a = v.analisis_miniatura
                        analisis_individuales.append(
                            f"- {comp.nombre}: \"{v.titulo}\" ({v.vistas:,} vistas)\n"
                            f"    Estilo: {a.estilo_general or '?'}\n"
                            f"    Colores: {', '.join(a.colores_dominantes[:3])}, "
                            f"Rostro: {'si' if a.tiene_rostro else 'no'}"
                            f"{', ' + a.expresion_facial if a.expresion_facial else ''}, "
                            f"Texto: {'si' if a.tiene_texto_overlay else 'no'}, "
                            f"Composicion: {a.composicion or '?'}"
                        )

            if analisis_individuales:
                user_prompt += f"""

MINIATURAS REALES DE COMPETIDORES TOP (analisis visual):
{chr(10).join(analisis_individuales)}

Diferenciarte de estas miniaturas MANTENIENDO los elementos que funcionan
(colores, composicion) pero con un estilo visual propio."""

        except FileNotFoundError:
            pass

    user_prompt += "\n\nDisena la miniatura para este video."

    user_prompt = inyectar_knowledge(user_prompt, "depto_1_estrategia")
    resultado = generar_json(system_prompt, user_prompt)

    resultado = revisar_con_claude(resultado, f"""Revisa esta composicion de miniatura para YouTube.
Titulo del video: {titulo}
Nicho: {nicho}

Verifica y mejora si es necesario:
1. texto_principal tiene maximo 5 palabras y es impactante para CTR
2. prompt_imagen es detallado, en ingles, y no incluye texto overlay
3. La paleta genera contraste y atencion visual
4. El elemento_focal es claro y atractivo

Devuelve el JSON con las mismas claves: fondo, texto_principal, posicion_texto, paleta, elemento_focal, prompt_imagen""")

    miniatura_composicion = {
        "fondo": resultado.get("fondo"),
        "texto_principal": resultado.get("texto_principal"),
        "posicion_texto": resultado.get("posicion_texto"),
        "paleta": resultado.get("paleta"),
        "elemento_focal": resultado.get("elemento_focal"),
    }
    miniatura_prompt_raw = resultado.get("prompt_imagen", "")

    if identidad and identidad.prompt_template:
        miniatura_prompt, miniatura_negative = aplicar_estilo_custom(
            identidad.prompt_template, identidad.negative_prompt, miniatura_prompt_raw
        )
    elif identidad:
        miniatura_prompt, miniatura_negative = aplicar_estilo(
            identidad.estilo_slug, miniatura_prompt_raw
        )
    else:
        miniatura_prompt = miniatura_prompt_raw
        miniatura_negative = ""

    state.actualizar(
        request.proyecto_id,
        estrategia={
            "miniatura_prompt": miniatura_prompt,
            "miniatura_negative": miniatura_negative,
            "miniatura_composicion": miniatura_composicion,
        },
    )
    return {
        "miniatura_prompt": miniatura_prompt,
        "miniatura_negative": miniatura_negative,
        "miniatura_composicion": miniatura_composicion,
        "identidad_canal_usada": identidad is not None,
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
