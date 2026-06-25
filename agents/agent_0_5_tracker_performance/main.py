"""
Agente 0.5 - Tracker de Performance
Depto 0 (Inteligencia de Canal)

Analiza el rendimiento de videos YA PUBLICADOS en 5 checkpoints progresivos:

  T+24h  → Alerta temprana (CTR, views iniciales, retention)
  T+48h  → Tendencia (creciendo o cayendo, engagement)
  T+72h  → Traffic sources y demografia
  T+7d   → Baseline estable, grade completo
  T+30d  → Evaluacion definitiva, patrones a replicar/evitar

Cada checkpoint genera acciones concretas, no solo datos:
  - Si CTR < umbral y retention > 50% → sugerir cambio de thumbnail/titulo
  - Si views creciendo → registrar patron exitoso para replicar
  - Si views cayendo → registrar patron a evitar

Los umbrales son adaptativos: se comparan contra el promedio del canal
ademas de los absolutos. Despues de 5+ videos, los relativos dominan.
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
from shared.logger import get_logger
from shared.schemas import (
    CHECKPOINT_HORAS,
    AccionCorrectiva,
    AgenteRequest,
    AgenteResponse,
    CheckpointTipo,
    DemografiaAudiencia,
    GradePerformance,
    MetricasVideo,
    PerformanceCheckpoint,
    PerformanceTracking,
    TrafficSources,
)
from shared.state_manager import StateManager
from shared.youtube_client import (
    oauth_disponible,
    obtener_analytics_video,
    obtener_demografia,
    obtener_impressions_ctr,
    obtener_metricas_videos,
    obtener_traffic_sources,
)

AGENTE_ID = "0.5_tracker_performance"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Trackea performance post-publicacion en 5 checkpoints")
channels = ChannelManager()
state = StateManager()
log = get_logger(AGENTE_ID)

# ── Umbrales absolutos (punto de partida) ──────────────────────

UMBRALES = {
    "ctr_excelente": 8.0,
    "ctr_bueno": 5.0,
    "ctr_pobre": 3.0,
    "retencion_excelente": 60.0,
    "retencion_buena": 50.0,
    "retencion_critica": 30.0,
    "engagement_excelente": 8.0,
    "engagement_bueno": 5.0,
    "engagement_pobre": 2.0,
}

# ── Logica principal ──────────────────────────────────────────

def logica(request: AgenteRequest) -> dict:
    proyecto_id = request.proyecto_id
    video_id = request.parametros.get("video_id", "")
    canal_id = request.parametros.get("canal_id", "")
    checkpoint_tipo = request.parametros.get("checkpoint", "")

    if not video_id:
        raise ValueError("Falta 'video_id' en parametros")
    if not canal_id:
        raise ValueError("Falta 'canal_id' en parametros")
    if not checkpoint_tipo:
        raise ValueError("Falta 'checkpoint' en parametros (t_24h, t_48h, t_72h, t_7d, t_30d)")

    tipo = CheckpointTipo(checkpoint_tipo)

    proyecto = state.leer(proyecto_id)
    canal = channels.leer(canal_id)

    fecha_pub = proyecto.publicado_en
    if not fecha_pub:
        raise ValueError(f"El proyecto {proyecto_id} no tiene fecha de publicacion")

    fecha_inicio = fecha_pub.strftime("%Y-%m-%d")
    fecha_fin = datetime.utcnow().strftime("%Y-%m-%d")

    log.info("checkpoint %s | video=%s | canal=%s", tipo.value, video_id, canal_id)

    # ── 1. Recoger metricas de Data API v3 (siempre disponible) ──
    metricas_data = obtener_metricas_videos([video_id])
    if not metricas_data:
        raise ValueError(f"No se encontro el video {video_id} en YouTube")

    v = metricas_data[0]
    engagement_rate = 0.0
    if v["vistas"] > 0:
        engagement_rate = round(((v["likes"] + v["comentarios"]) / v["vistas"]) * 100, 2)

    metricas = MetricasVideo(
        vistas=v["vistas"],
        likes=v["likes"],
        comentarios=v["comentarios"],
        engagement_rate=engagement_rate,
    )

    # ── 2. Analytics API v2 (si OAuth esta disponible) ──
    traffic = None
    demo = None

    if oauth_disponible():
        try:
            analytics = obtener_analytics_video(video_id, fecha_inicio, fecha_fin)
            metricas.retencion_promedio = analytics.get("retencion_promedio")
            metricas.tiempo_visto_min = analytics.get("tiempo_visto_min")
            metricas.duracion_vista_promedio_seg = analytics.get("duracion_vista_promedio_seg")
        except Exception as e:
            log.warning("analytics basico no disponible: %s", e)

        try:
            ctr_data = obtener_impressions_ctr(video_id, fecha_inicio, fecha_fin)
            metricas.ctr = ctr_data.get("ctr")
        except Exception as e:
            log.warning("CTR no disponible: %s", e)

        if tipo in (CheckpointTipo.T_72H, CheckpointTipo.T_7D, CheckpointTipo.T_30D):
            try:
                ts = obtener_traffic_sources(video_id, fecha_inicio, fecha_fin)
                traffic = TrafficSources(**ts)
            except Exception as e:
                log.warning("traffic sources no disponible: %s", e)

            try:
                dem = obtener_demografia(video_id, fecha_inicio, fecha_fin)
                demo = DemografiaAudiencia(**dem)
            except Exception as e:
                log.warning("demografia no disponible: %s", e)

    # ── 3. Calcular tendencia de vistas (comparar vs checkpoint anterior) ──
    tendencia = _calcular_tendencia(proyecto, metricas.vistas)

    # ── 4. Comparar contra promedios del canal ──
    promedios = canal.promedios_canal
    vs_promedio = _comparar_vs_canal(metricas, promedios)

    # ── 5. Calcular grade y score ──
    score = _calcular_score(metricas, promedios)
    grade = _score_a_grade(score)

    # ── 6. Generar insights y acciones concretas ──
    insights = _generar_insights(tipo, metricas, vs_promedio, traffic)
    acciones = _generar_acciones(tipo, metricas, vs_promedio, proyecto.estrategia.titulo_ganador or "")

    # ── 7. Armar el checkpoint ──
    checkpoint = PerformanceCheckpoint(
        tipo=tipo,
        timestamp=datetime.utcnow(),
        metricas=metricas,
        tendencia_vistas=tendencia,
        traffic_sources=traffic,
        demografia=demo,
        grade=grade,
        score=score,
        vs_promedio_canal=vs_promedio,
        insights=insights,
        acciones=acciones,
    )

    # ── 7. Persistir en el proyecto ──
    if not proyecto.performance:
        proyecto.performance = PerformanceTracking(
            video_id=video_id,
            proyecto_id=proyecto_id,
            canal_id=canal_id,
            titulo=proyecto.estrategia.titulo_ganador or "",
            publicado_en=fecha_pub,
        )

    proyecto.performance.checkpoints.append(checkpoint)
    proyecto.performance.grade_actual = grade
    state.guardar(proyecto)

    # ── 8. Actualizar promedios del canal (T+7d y T+30d) ──
    if tipo in (CheckpointTipo.T_7D, CheckpointTipo.T_30D):
        _actualizar_promedios_canal(canal_id, metricas)
        _registrar_patrones(canal_id, metricas, vs_promedio, proyecto)

    log.info(
        "checkpoint %s completado | video=%s | score=%s | grade=%s | acciones=%d",
        tipo.value, video_id, score, grade.value if grade else "?", len(acciones),
    )

    return {
        "checkpoint": tipo.value,
        "video_id": video_id,
        "score": score,
        "grade": grade.value if grade else None,
        "insights": insights,
        "acciones_count": len(acciones),
        "acciones": [a.model_dump() for a in acciones],
    }


# ── Tendencia de vistas ───────────────────────────────────────

def _calcular_tendencia(proyecto, vistas_actuales: int) -> str | None:
    """Compara vistas actuales vs el checkpoint anterior para determinar tendencia."""
    if not proyecto.performance or not proyecto.performance.checkpoints:
        return None
    vistas_anterior = proyecto.performance.checkpoints[-1].metricas.vistas
    if vistas_anterior == 0:
        return "creciendo" if vistas_actuales > 0 else "estable"
    ratio = vistas_actuales / vistas_anterior
    if ratio >= 1.3:
        return "creciendo"
    if ratio <= 0.95:
        return "cayendo"
    return "estable"


# ── Comparacion vs promedio del canal ─────────────────────────

def _comparar_vs_canal(metricas: MetricasVideo, promedios) -> dict:
    vs = {}
    if promedios.total_videos_analizados < 3:
        vs["nota"] = "menos de 3 videos analizados, usando solo umbrales absolutos"
        return vs

    if promedios.vistas_promedio > 0:
        vs["vistas_vs_promedio"] = round((metricas.vistas / promedios.vistas_promedio) * 100, 1)

    if promedios.ctr_promedio and metricas.ctr is not None:
        vs["ctr_vs_promedio"] = round(metricas.ctr - promedios.ctr_promedio, 2)

    if promedios.retencion_promedio and metricas.retencion_promedio is not None:
        vs["retencion_vs_promedio"] = round(metricas.retencion_promedio - promedios.retencion_promedio, 2)

    if promedios.engagement_rate_promedio and metricas.engagement_rate is not None:
        vs["engagement_vs_promedio"] = round(metricas.engagement_rate - promedios.engagement_rate_promedio, 2)

    return vs


# ── Score y grade ─────────────────────────────────────────────

def _calcular_score(metricas: MetricasVideo, promedios) -> float:
    score = 50.0

    if metricas.ctr is not None:
        if metricas.ctr >= UMBRALES["ctr_excelente"]:
            score += 15
        elif metricas.ctr >= UMBRALES["ctr_bueno"]:
            score += 8
        elif metricas.ctr < UMBRALES["ctr_pobre"]:
            score -= 15

    if metricas.retencion_promedio is not None:
        if metricas.retencion_promedio >= UMBRALES["retencion_excelente"]:
            score += 15
        elif metricas.retencion_promedio >= UMBRALES["retencion_buena"]:
            score += 8
        elif metricas.retencion_promedio < UMBRALES["retencion_critica"]:
            score -= 15

    if metricas.engagement_rate is not None:
        if metricas.engagement_rate >= UMBRALES["engagement_excelente"]:
            score += 10
        elif metricas.engagement_rate >= UMBRALES["engagement_bueno"]:
            score += 5
        elif metricas.engagement_rate < UMBRALES["engagement_pobre"]:
            score -= 10

    # Bonus/penalizacion relativa al canal
    if promedios.total_videos_analizados >= 3 and promedios.vistas_promedio > 0:
        ratio_vistas = metricas.vistas / promedios.vistas_promedio
        if ratio_vistas >= 2.0:
            score += 10
        elif ratio_vistas >= 1.3:
            score += 5
        elif ratio_vistas < 0.5:
            score -= 10

    return max(0, min(100, round(score, 1)))


def _score_a_grade(score: float) -> GradePerformance:
    if score >= 90:
        return GradePerformance.A_PLUS
    if score >= 80:
        return GradePerformance.A
    if score >= 65:
        return GradePerformance.B
    if score >= 50:
        return GradePerformance.C
    if score >= 35:
        return GradePerformance.D
    return GradePerformance.F


# ── Insights ──────────────────────────────────────────────────

def _generar_insights(
    tipo: CheckpointTipo,
    metricas: MetricasVideo,
    vs_promedio: dict,
    traffic: TrafficSources | None,
) -> list[str]:
    insights = []

    if metricas.ctr is not None:
        if metricas.ctr >= UMBRALES["ctr_excelente"]:
            insights.append(f"CTR excelente ({metricas.ctr}%) — thumbnail y titulo funcionan muy bien")
        elif metricas.ctr < UMBRALES["ctr_pobre"]:
            insights.append(f"CTR pobre ({metricas.ctr}%) — thumbnail o titulo no atraen clicks")

    if metricas.retencion_promedio is not None:
        if metricas.retencion_promedio >= UMBRALES["retencion_excelente"]:
            insights.append(f"Retencion excelente ({metricas.retencion_promedio}%) — el contenido engancha")
        elif metricas.retencion_promedio < UMBRALES["retencion_critica"]:
            insights.append(f"Retencion critica ({metricas.retencion_promedio}%) — audiencia abandona rapido")

    if metricas.ctr is not None and metricas.retencion_promedio is not None:
        if metricas.ctr < UMBRALES["ctr_pobre"] and metricas.retencion_promedio >= UMBRALES["retencion_buena"]:
            insights.append("Buen contenido pero mal empaque — el video es bueno pero no atrae clicks")
        elif metricas.ctr >= UMBRALES["ctr_bueno"] and metricas.retencion_promedio < UMBRALES["retencion_critica"]:
            insights.append("Buen empaque pero contenido debil — atrae clicks pero no retiene")

    ratio = vs_promedio.get("vistas_vs_promedio")
    if ratio is not None:
        if ratio >= 200:
            insights.append(f"Views al {ratio}% del promedio del canal — rendimiento excepcional")
        elif ratio < 50:
            insights.append(f"Views al {ratio}% del promedio del canal — bajo rendimiento")

    if traffic:
        if traffic.search >= 30:
            insights.append(f"SEO fuerte: {traffic.search}% del trafico viene de busqueda")
        if traffic.suggested >= 40:
            insights.append(f"Algoritmo a favor: {traffic.suggested}% viene de sugeridos")
        if traffic.browse >= 25:
            insights.append(f"Home push: {traffic.browse}% viene del feed de inicio")

    return insights


# ── Acciones correctivas ─────────────────────────────────────

def _generar_acciones(
    tipo: CheckpointTipo,
    metricas: MetricasVideo,
    vs_promedio: dict,
    titulo_actual: str,
) -> list[AccionCorrectiva]:
    acciones = []

    # T+24h: Accion rapida sobre thumbnail/titulo
    if tipo == CheckpointTipo.T_24H:
        if metricas.ctr is not None and metricas.ctr < UMBRALES["ctr_pobre"]:
            buen_contenido = (
                metricas.retencion_promedio is not None
                and metricas.retencion_promedio >= UMBRALES["retencion_buena"]
            )
            if buen_contenido:
                acciones.append(AccionCorrectiva(
                    tipo="cambiar_thumbnail",
                    prioridad="alta",
                    descripcion=(
                        f"CTR de {metricas.ctr}% pero retencion de {metricas.retencion_promedio}%. "
                        "El video es bueno pero el thumbnail/titulo no atraen. "
                        "Generar alternativas urgente."
                    ),
                    agente_destino="1.4_generador_miniatura",
                    datos={"titulo_actual": titulo_actual, "ctr_actual": metricas.ctr},
                ))
                acciones.append(AccionCorrectiva(
                    tipo="cambiar_titulo",
                    prioridad="alta",
                    descripcion="Generar titulo alternativo con diferente angulo/gancho.",
                    agente_destino="1.2_copywriter",
                    datos={"titulo_actual": titulo_actual, "ctr_actual": metricas.ctr},
                ))
            else:
                acciones.append(AccionCorrectiva(
                    tipo="cambiar_thumbnail",
                    prioridad="media",
                    descripcion=f"CTR bajo ({metricas.ctr}%). Probar thumbnail alternativo.",
                    agente_destino="1.4_generador_miniatura",
                    datos={"titulo_actual": titulo_actual, "ctr_actual": metricas.ctr},
                ))

    # T+48h: Tendencia
    if tipo == CheckpointTipo.T_48H:
        ratio = vs_promedio.get("vistas_vs_promedio")
        if ratio is not None and ratio < 50:
            acciones.append(AccionCorrectiva(
                tipo="ajustar_estrategia",
                prioridad="media",
                descripcion=(
                    f"Views al {ratio}% del promedio del canal tras 48h. "
                    "Registrar tema/formato como bajo alcance para futuros videos."
                ),
                agente_destino="0.4_asesor_estrategico",
                datos={"ratio_vistas": ratio},
            ))
        elif ratio is not None and ratio >= 150:
            acciones.append(AccionCorrectiva(
                tipo="replicar_patron",
                prioridad="media",
                descripcion=(
                    f"Views al {ratio}% del promedio — alto potencial. "
                    "Registrar tema/formato como exitoso para replicar."
                ),
                agente_destino="0.4_asesor_estrategico",
                datos={"ratio_vistas": ratio},
            ))

    # T+72h: SEO feedback
    if tipo == CheckpointTipo.T_72H:
        if metricas.ctr is not None and metricas.ctr < UMBRALES["ctr_pobre"]:
            acciones.append(AccionCorrectiva(
                tipo="mejorar_seo",
                prioridad="media",
                descripcion="CTR sigue bajo despues de 72h. Revisar tags y descripcion.",
                agente_destino="5.2_seo",
                datos={"ctr_actual": metricas.ctr},
            ))

    # T+7d y T+30d: Evaluacion completa
    if tipo in (CheckpointTipo.T_7D, CheckpointTipo.T_30D):
        if metricas.ctr is not None and metricas.ctr >= UMBRALES["ctr_excelente"]:
            acciones.append(AccionCorrectiva(
                tipo="replicar_patron",
                prioridad="alta",
                descripcion=f"CTR de {metricas.ctr}% — registrar patron de titulo/thumbnail exitoso.",
                agente_destino="1.2_copywriter",
                datos={"titulo": titulo_actual, "ctr": metricas.ctr},
            ))
        if metricas.engagement_rate is not None and metricas.engagement_rate >= UMBRALES["engagement_excelente"]:
            acciones.append(AccionCorrectiva(
                tipo="replicar_patron",
                prioridad="media",
                descripcion=f"Engagement de {metricas.engagement_rate}% — el formato conecta con la audiencia.",
                agente_destino="0.4_asesor_estrategico",
                datos={"engagement": metricas.engagement_rate},
            ))

    return acciones


# ── Actualizacion de promedios del canal ──────────────────────

def _actualizar_promedios_canal(canal_id: str, metricas: MetricasVideo) -> None:
    try:
        canal = channels.leer(canal_id)
        p = canal.promedios_canal
        n = p.total_videos_analizados

        p.vistas_promedio = ((p.vistas_promedio * n) + metricas.vistas) / (n + 1)
        p.likes_promedio = ((p.likes_promedio * n) + metricas.likes) / (n + 1)
        p.comentarios_promedio = ((p.comentarios_promedio * n) + metricas.comentarios) / (n + 1)

        if metricas.ctr is not None:
            ctr_actual = p.ctr_promedio or 0.0
            p.ctr_promedio = ((ctr_actual * n) + metricas.ctr) / (n + 1)

        if metricas.retencion_promedio is not None:
            ret_actual = p.retencion_promedio or 0.0
            p.retencion_promedio = ((ret_actual * n) + metricas.retencion_promedio) / (n + 1)

        if metricas.engagement_rate is not None:
            eng_actual = p.engagement_rate_promedio or 0.0
            p.engagement_rate_promedio = ((eng_actual * n) + metricas.engagement_rate) / (n + 1)

        p.total_videos_analizados = n + 1
        p.actualizado_en = datetime.utcnow()

        channels.actualizar(canal_id, promedios_canal=p.model_dump())
        log.info("promedios canal actualizados | n=%d | vistas_avg=%.0f", n + 1, p.vistas_promedio)
    except Exception as e:
        log.error("error actualizando promedios: %s", e)


# ── Registro de patrones ──────────────────────────────────────

def _registrar_patrones(canal_id: str, metricas: MetricasVideo, vs_promedio: dict, proyecto) -> None:
    try:
        canal = channels.leer(canal_id)
        titulo = proyecto.estrategia.titulo_ganador or ""
        nicho = proyecto.estrategia.nicho or ""

        ratio = vs_promedio.get("vistas_vs_promedio", 100)

        entry = {
            "titulo": titulo,
            "nicho": nicho,
            "vistas": metricas.vistas,
            "ctr": metricas.ctr,
            "retencion": metricas.retencion_promedio,
            "engagement": metricas.engagement_rate,
            "ratio_vs_promedio": ratio,
            "fecha": datetime.utcnow().isoformat(),
        }

        if ratio >= 150:
            patrones = canal.patrones_exitosos
            patrones.append(entry)
            channels.actualizar(canal_id, patrones_exitosos=patrones[-20:])
            log.info("patron exitoso registrado: %s", titulo)
        elif ratio < 50:
            patrones = canal.patrones_a_evitar
            patrones.append(entry)
            channels.actualizar(canal_id, patrones_a_evitar=patrones[-20:])
            log.info("patron a evitar registrado: %s", titulo)

        historial = canal.performance_historial
        historial.append(entry)
        channels.actualizar(canal_id, performance_historial=historial[-50:])
    except Exception as e:
        log.error("error registrando patrones: %s", e)


# ── Endpoint FastAPI ──────────────────────────────────────────

ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
