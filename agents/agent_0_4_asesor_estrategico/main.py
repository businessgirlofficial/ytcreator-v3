"""
Agente 0.4 - Asesor Estrategico
Depto 0 (Inteligencia de Canal)

Combina toda la inteligencia del canal (perfil + competidores +
tendencias + brechas) para generar:
  - 5-10 ideas de video rankeadas por potencial viral
  - Formulas de titulo recomendadas
  - Estilo de miniatura sugerido
  - Calendario de publicacion optimo
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.channel_manager import ChannelManager
from shared.config import REGISTRO_AGENTES
from shared.groq_client import generar_json
from shared.knowledge_loader import inyectar_knowledge
from shared.schemas import AgenteRequest, AgenteResponse

AGENTE_ID = "0.4_asesor_estrategico"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Genera ideas de video rankeadas basadas en inteligencia del canal")
channels = ChannelManager()

SYSTEM_PROMPT = """Eres un asesor estrategico de YouTube con acceso a datos reales de un
canal y su competencia. Tu trabajo es generar ideas de video CONCRETAS y
accionables, rankeadas por potencial viral.

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "ideas": [
    {
      "titulo_sugerido": "titulo clickeable y optimizado",
      "tema": "descripcion breve del tema (1-2 frases)",
      "potencial_viral": 8.5,
      "razon": "por que esta idea tiene potencial viral (basado en datos reales)",
      "formato_recomendado": "listicle/storytime/tutorial/etc",
      "duracion_sugerida_min": 10
    }
  ],
  "formulas_titulo": ["formula 1 con placeholders (ej: '{numero} {cosa} que {resultado}')", "formula 2"],
  "estilo_miniatura": "descripcion del estilo de miniatura que mejor funciona en este nicho",
  "calendario": "recomendacion de frecuencia y mejores dias/horarios"
}

Genera entre 5 y 10 ideas, ordenadas por potencial_viral (mayor a menor).
El potencial_viral es un score de 1.0 a 10.0.
Basa todo en los DATOS proporcionados. Las ideas deben explotar brechas
de contenido y tendencias detectadas."""


def logica(request: AgenteRequest) -> dict:
    canal_id = request.parametros.get("canal_id", "")
    if not canal_id:
        raise ValueError("Falta el parametro 'canal_id'")

    estado = channels.leer(canal_id)
    perfil = estado.perfil

    top_titulos = [f"{v.titulo} ({v.vistas:,} vistas)" for v in estado.top_videos[:10]]

    comp_info = []
    for comp in estado.competidores[:5]:
        comp_top = [f"{v.titulo} ({v.vistas:,} vistas)" for v in comp.top_videos[:3]]
        comp_info.append(f"- {comp.nombre} ({comp.suscriptores or '?'} subs): {', '.join(comp_top) if comp_top else 'N/A'}")

    # Performance feedback: patrones exitosos y a evitar
    exitosos_info = []
    for p in estado.patrones_exitosos[-5:]:
        exitosos_info.append(
            f"- \"{p.get('titulo', '?')}\" → {p.get('vistas', 0):,} vistas, "
            f"CTR {p.get('ctr', '?')}%, retencion {p.get('retencion', '?')}%"
        )

    evitar_info = []
    for p in estado.patrones_a_evitar[-5:]:
        evitar_info.append(
            f"- \"{p.get('titulo', '?')}\" → {p.get('vistas', 0):,} vistas, "
            f"CTR {p.get('ctr', '?')}%, retencion {p.get('retencion', '?')}%"
        )

    promedios = estado.promedios_canal
    promedios_info = "(sin datos suficientes)"
    if promedios.total_videos_analizados >= 3:
        promedios_info = (
            f"Vistas promedio: {promedios.vistas_promedio:,.0f} | "
            f"CTR promedio: {promedios.ctr_promedio or '?'}% | "
            f"Retencion promedio: {promedios.retencion_promedio or '?'}% | "
            f"Engagement promedio: {promedios.engagement_rate_promedio or '?'}% | "
            f"Videos analizados: {promedios.total_videos_analizados}"
        )

    user_prompt = f"""Canal: {estado.nombre}
Nicho: {perfil.nicho_principal or 'sin determinar'}
Sub-nichos: {', '.join(perfil.sub_nichos) if perfil.sub_nichos else 'N/A'}
Tono: {perfil.tono or 'sin determinar'}
Audiencia: {perfil.audiencia_objetivo or 'sin determinar'}
Formatos que funcionan: {', '.join(perfil.formatos_exitosos) if perfil.formatos_exitosos else 'N/A'}
Frecuencia actual: {perfil.frecuencia_publicacion or 'N/A'}
Duracion promedio: {perfil.duracion_promedio_seg or 'N/A'} segundos

Metricas promedio del canal (performance real):
{promedios_info}

Patrones de titulo exitosos del canal:
{chr(10).join(f'- {p}' for p in perfil.patrones_titulo_exitosos) if perfil.patrones_titulo_exitosos else '(sin datos)'}

Top 10 videos del canal:
{chr(10).join(f'- {t}' for t in top_titulos) if top_titulos else '(sin datos)'}

Videos con MEJOR performance (REPLICAR estos patrones):
{chr(10).join(exitosos_info) if exitosos_info else '(sin datos aun)'}

Videos con PEOR performance (EVITAR estos patrones):
{chr(10).join(evitar_info) if evitar_info else '(sin datos aun)'}

Competidores y sus top videos:
{chr(10).join(comp_info) if comp_info else '(sin competidores)'}

Tendencias del nicho:
{chr(10).join(f'- {t}' for t in estado.tendencias_nicho) if estado.tendencias_nicho else '(sin tendencias)'}

Brechas de contenido (temas no cubiertos por el canal):
{chr(10).join(f'- {b}' for b in estado.brechas_contenido) if estado.brechas_contenido else '(sin brechas detectadas)'}

Genera ideas de video rankeadas por potencial viral, aprovechando las
brechas y tendencias. PRIORIZA patrones que ya funcionaron y EVITA
los que tuvieron bajo rendimiento. Adapta al tono y formatos que funcionan."""

    user_prompt = inyectar_knowledge(user_prompt, "depto_0_inteligencia")
    resultado = generar_json(SYSTEM_PROMPT, user_prompt)

    ideas = resultado.get("ideas", [])
    ideas_ordenadas = sorted(ideas, key=lambda i: i.get("potencial_viral", 0), reverse=True)

    channels.actualizar(
        canal_id,
        ideas_sugeridas=ideas_ordenadas,
    )

    return {
        "canal_id": canal_id,
        "ideas_generadas": len(ideas_ordenadas),
        "top_idea": ideas_ordenadas[0].get("titulo_sugerido") if ideas_ordenadas else None,
        "formulas_titulo": resultado.get("formulas_titulo", []),
        "estilo_miniatura": resultado.get("estilo_miniatura"),
        "calendario": resultado.get("calendario"),
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
