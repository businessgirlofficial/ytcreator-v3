"""
Agente 0.3 - Monitor de Mercado
Depto 0 (Inteligencia de Canal)

Monitorea la competencia del canal y detecta tendencias:
  1. Discovery hibrido: busca competidores automaticamente (search.list)
     O acepta competidores agregados manualmente
  2. Escanea videos recientes de cada competidor
  3. Analiza con Groq: tendencias cruzadas, brechas de contenido,
     patrones virales reales del nicho
  4. Complementa con DuckDuckGo (0 cost)
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.channel_manager import ChannelManager
from shared.config import REGISTRO_AGENTES
from shared.groq_client import generar_json
from shared.knowledge_loader import inyectar_knowledge
from shared.schemas import (
    AgenteRequest,
    AgenteResponse,
    CompetidorInfo,
    VideoRendimiento,
)
from shared.web_search import buscar
from shared.youtube_client import (
    buscar_canales_relacionados,
    obtener_canal,
    obtener_metricas_videos,
    obtener_videos_recientes,
)

AGENTE_ID = "0.3_monitor_mercado"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Monitorea competencia y detecta tendencias del nicho")
channels = ChannelManager()

MAX_COMPETIDORES = 5
MAX_CANDIDATOS_DISCOVERY = 20
REFRESCO_COMPETIDORES_HORAS = 48

SYSTEM_PROMPT = """Eres un analista de mercado de YouTube especializado en detectar
tendencias y oportunidades. Recibes datos de un canal y sus competidores.

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "tendencias_nicho": ["tendencia 1 concreta y accionable", "tendencia 2", "tendencia 3"],
  "brechas_contenido": ["tema que el canal NO ha cubierto pero competidores si", "brecha 2"],
  "brechas_inversas": ["tema que el canal cubre pero competidores no (ventaja competitiva)"],
  "patrones_virales": ["patron viral concreto observado en los datos (ej: 'titulos con numeros obtienen 2x vistas')"],
  "oportunidades": ["oportunidad 1 especifica para crear contenido", "oportunidad 2"]
}

Se concreto. Basa todo en los DATOS proporcionados, no en consejos genericos."""


def _parsear_fecha(valor) -> datetime | None:
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _escanear_competidor(channel_id: str) -> CompetidorInfo:
    canal_data = obtener_canal(channel_id)
    comp = CompetidorInfo(
        channel_id=canal_data["id"],
        nombre=canal_data["nombre"],
        suscriptores=canal_data.get("suscriptores"),
        video_count=canal_data.get("video_count"),
        creado_youtube=_parsear_fecha(canal_data.get("creado_youtube")),
        ultimo_escaneo=datetime.utcnow(),
    )

    uploads = canal_data.get("uploads_playlist_id")
    if uploads:
        video_ids = obtener_videos_recientes(uploads, max_videos=20)
        if video_ids:
            videos_data = obtener_metricas_videos(video_ids)
            videos = [
                VideoRendimiento(
                    video_id=v["video_id"],
                    titulo=v["titulo"],
                    publicado_en=v.get("publicado_en"),
                    vistas=v.get("vistas", 0),
                    likes=v.get("likes", 0),
                    comentarios=v.get("comentarios", 0),
                    duracion_seg=v.get("duracion_seg"),
                    tags=v.get("tags", []),
                )
                for v in videos_data
            ]
            comp.videos_recientes = videos
            comp.top_videos = sorted(videos, key=lambda v: v.vistas, reverse=True)[:5]

    return comp


def _cumple_criterios_ganador(comp: CompetidorInfo) -> int:
    """
    Evalua cuantos criterios de 'canal ganador' cumple (0-4).
    Criterios del curso Tu Imperio YouTube:
      - Menos de 90 videos
      - Menos de 100,000 suscriptores
      - Menos de 90 dias de creado
      - Vistas promedio entre 10,000 y 100,000
    """
    score = 0
    if comp.video_count is not None and comp.video_count < 90:
        score += 1
    if comp.suscriptores is not None and comp.suscriptores < 100_000:
        score += 1
    if comp.creado_youtube is not None:
        dias = (datetime.utcnow() - comp.creado_youtube).days
        if dias < 90:
            score += 1
    if comp.videos_recientes:
        vistas = [v.vistas for v in comp.videos_recientes if v.vistas > 0]
        if vistas:
            promedio = sum(vistas) / len(vistas)
            if 10_000 <= promedio <= 100_000:
                score += 1
    return score


def _discovery_automatico(
    nicho: str,
    subnicho: str,
    keywords: list[str],
    canal_propio_id: str,
) -> list[CompetidorInfo]:
    queries = []
    if subnicho:
        queries.append(f"{subnicho} youtube")
    queries.append(f"{nicho} youtube {' '.join(keywords[:3])}")
    if subnicho and keywords:
        queries.append(f"{subnicho} {keywords[0]} youtube")

    candidatos_ids: set[str] = set()
    candidatos_raw: list[dict] = []

    for query in queries:
        try:
            resultados = buscar_canales_relacionados(query, max_resultados=10)
        except Exception:
            continue
        for r in resultados:
            cid = r["channel_id"]
            if cid != canal_propio_id and cid not in candidatos_ids:
                candidatos_ids.add(cid)
                candidatos_raw.append(r)
        if len(candidatos_raw) >= MAX_CANDIDATOS_DISCOVERY:
            break

    candidatos_escaneados: list[CompetidorInfo] = []
    for raw in candidatos_raw[:MAX_CANDIDATOS_DISCOVERY]:
        try:
            comp = _escanear_competidor(raw["channel_id"])
            candidatos_escaneados.append(comp)
        except Exception:
            pass

    candidatos_escaneados.sort(
        key=lambda c: _cumple_criterios_ganador(c), reverse=True,
    )

    return candidatos_escaneados[:MAX_COMPETIDORES]


def _busqueda_web_tendencias(nicho: str) -> str:
    try:
        resultados = buscar(f"tendencias {nicho} youtube 2024 2025", max_resultados=5)
    except Exception:
        return "(busqueda web no disponible)"
    if not resultados:
        return "(sin resultados de busqueda web)"
    return "\n".join(f"- {r['titulo']}: {r['resumen']}" for r in resultados)


def logica(request: AgenteRequest) -> dict:
    canal_id = request.parametros.get("canal_id", "")
    if not canal_id:
        raise ValueError("Falta el parametro 'canal_id'")

    forzar_discovery = request.parametros.get("forzar_discovery", False)

    estado = channels.leer(canal_id)
    perfil = estado.perfil

    competidores_actuales = estado.competidores
    necesita_discovery = not competidores_actuales or forzar_discovery

    if necesita_discovery and perfil.nicho_principal:
        descubiertos = _discovery_automatico(
            perfil.nicho_principal,
            perfil.subnicho_principal,
            perfil.keywords_clave,
            canal_id,
        )
        ids_existentes = {c.channel_id for c in competidores_actuales}
        for comp in descubiertos:
            if comp.channel_id not in ids_existentes and len(competidores_actuales) < MAX_COMPETIDORES:
                competidores_actuales.append(comp)
                ids_existentes.add(comp.channel_id)

    competidores_actualizados = []
    for comp in competidores_actuales:
        necesita_refresco = (
            not comp.ultimo_escaneo
            or (datetime.utcnow() - comp.ultimo_escaneo) > timedelta(hours=REFRESCO_COMPETIDORES_HORAS)
        )
        if necesita_refresco:
            try:
                comp = _escanear_competidor(comp.channel_id)
            except Exception:
                pass
        competidores_actualizados.append(comp)

    canal_titulos = [v.titulo for v in estado.videos_recientes[:15]]
    comp_resumen = []
    for comp in competidores_actualizados:
        score = _cumple_criterios_ganador(comp)
        top_titles = [v.titulo for v in comp.top_videos[:5]]
        recent_titles = [v.titulo for v in comp.videos_recientes[:10]]
        dias_creado = ""
        if comp.creado_youtube:
            dias_creado = f", {(datetime.utcnow() - comp.creado_youtube).days} dias de antiguedad"
        comp_resumen.append(
            f"Competidor: {comp.nombre} ({comp.suscriptores or '?'} subs, "
            f"{comp.video_count or '?'} videos{dias_creado}) "
            f"[Score canal ganador: {score}/4]\n"
            f"  Top videos: {', '.join(top_titles) if top_titles else 'N/A'}\n"
            f"  Recientes: {', '.join(recent_titles) if recent_titles else 'N/A'}"
        )

    busqueda_nicho = perfil.subnicho_principal or perfil.nicho_principal or canal_id
    tendencias_web = _busqueda_web_tendencias(busqueda_nicho)

    user_prompt = f"""Canal analizado: {estado.nombre}
Nicho: {perfil.nicho_principal or 'sin determinar'}
Subnicho: {perfil.subnicho_principal or 'sin determinar'}
Keywords: {', '.join(perfil.keywords_clave) if perfil.keywords_clave else 'N/A'}

Titulos recientes del canal:
{chr(10).join(f'- {t}' for t in canal_titulos) if canal_titulos else '(sin datos)'}

Competidores:
{chr(10).join(comp_resumen) if comp_resumen else '(sin competidores)'}

Tendencias web del nicho:
{tendencias_web}

Analiza la competencia, detecta tendencias y encuentra oportunidades."""

    user_prompt = inyectar_knowledge(user_prompt, "depto_0_inteligencia")
    resultado = generar_json(SYSTEM_PROMPT, user_prompt)

    channels.actualizar(
        canal_id,
        competidores=[c.model_dump() for c in competidores_actualizados],
        tendencias_nicho=resultado.get("tendencias_nicho", []),
        brechas_contenido=resultado.get("brechas_contenido", []),
        competidores_actualizados_en=datetime.utcnow().isoformat(),
    )

    return {
        "canal_id": canal_id,
        "competidores_monitoreados": len(competidores_actualizados),
        "tendencias": resultado.get("tendencias_nicho", []),
        "brechas": resultado.get("brechas_contenido", []),
        "oportunidades": resultado.get("oportunidades", []),
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
