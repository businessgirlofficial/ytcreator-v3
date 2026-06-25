"""
Orquestador central - YTCreator Studio
=========================================

Es el cerebro del sistema. No genera contenido el mismo: solo decide
en que orden llamar a cada departamento, valida que cada paso este
realmente completo antes de avanzar, y maneja la decision critica
mas importante del pipeline: si el guion no pasa el score minimo,
lo manda de vuelta al Guionista en vez de avanzar con un guion flojo.
"""

import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException

from shared.channel_manager import ChannelManager
from shared.config import REGISTRO_AGENTES, url_agente
from shared import event_store
from shared.health_checks import HealthCheckError, validar_fase, validar_todo
from shared.logger import get_logger
from shared.schemas import AgenteRequest
from shared.state_manager import StateManager

log = get_logger("orquestador_central")

app = FastAPI(title="Orquestador Central - YTCreator Studio")
state = StateManager()
channel_mgr = ChannelManager()

MAX_REINTENTOS_AGENTE = 3
BACKOFF_BASE = 5


def _llamar(agente_id: str, proyecto_id: str, parametros: dict | None = None) -> dict:
    request = AgenteRequest(proyecto_id=proyecto_id, parametros=parametros or {})
    ultimo_error = None
    inicio = datetime.utcnow()

    state.actualizar(proyecto_id, agente_actual=agente_id)
    log.info("llamando %s | proyecto=%s", agente_id, proyecto_id)

    for intento in range(1, MAX_REINTENTOS_AGENTE + 1):
        try:
            resp = httpx.post(
                f"{url_agente(agente_id)}/ejecutar",
                json=request.model_dump(),
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("estado") == "error":
                raise RuntimeError(f"{agente_id} fallo: {data.get('error')}")

            duracion = round((datetime.utcnow() - inicio).total_seconds(), 2)
            log.info("completado %s | proyecto=%s | duracion=%.2fs | intentos=%d", agente_id, proyecto_id, duracion, intento)
            event_store.registrar(
                "agent_completed", "success",
                source=agente_id, proyecto_id=proyecto_id,
                data={"intentos": intento},
                duration_seg=duracion,
            )
            state.registrar_resultado_agente(proyecto_id, {
                "agente_id": agente_id,
                "estado": "completado",
                "intentos": intento,
                "inicio": inicio.isoformat(),
                "fin": datetime.utcnow().isoformat(),
                "duracion_seg": duracion,
            })
            state.actualizar(proyecto_id, agente_actual=None)
            return data

        except Exception as exc:
            ultimo_error = exc
            if intento < MAX_REINTENTOS_AGENTE:
                espera = BACKOFF_BASE * intento
                log.warning("reintento %d/%d %s | proyecto=%s | error=%s", intento, MAX_REINTENTOS_AGENTE, agente_id, proyecto_id, exc)
                time.sleep(espera)

    duracion = round((datetime.utcnow() - inicio).total_seconds(), 2)
    log.error("fallo %s | proyecto=%s | duracion=%.2fs | %s", agente_id, proyecto_id, duracion, ultimo_error)
    event_store.registrar(
        "agent_failed", "error",
        source=agente_id, proyecto_id=proyecto_id,
        data={"error": str(ultimo_error), "intentos": MAX_REINTENTOS_AGENTE},
        duration_seg=duracion,
    )
    state.registrar_resultado_agente(proyecto_id, {
        "agente_id": agente_id,
        "estado": "error",
        "intentos": MAX_REINTENTOS_AGENTE,
        "inicio": inicio.isoformat(),
        "fin": datetime.utcnow().isoformat(),
        "duracion_seg": duracion,
        "error": str(ultimo_error),
    })
    state.actualizar(
        proyecto_id,
        agente_actual=None,
        errores=[f"{agente_id}: {ultimo_error} (tras {MAX_REINTENTOS_AGENTE} intentos)"],
    )
    raise RuntimeError(f"{agente_id} fallo tras {MAX_REINTENTOS_AGENTE} intentos: {ultimo_error}")


def _fase(proyecto_id: str, fase: str):
    state.actualizar(proyecto_id, fase_actual=fase)
    event_store.registrar(
        "pipeline_phase", "success",
        source="orquestador_central", proyecto_id=proyecto_id,
        data={"fase": fase},
    )


FASES_ORDEN = ["estrategia", "guion", "visual", "audio", "cierre", "completado", "publicado"]


def _archivo_existe(ruta: str | None) -> bool:
    """Verifica que un archivo exista en disco y no este vacio."""
    if not ruta:
        return False
    p = Path(ruta)
    return p.exists() and p.stat().st_size > 0


def _fase_completada(proyecto_id: str, fase_objetivo: str) -> bool:
    """Verifica si una fase ya fue completada revisando el estado del proyecto
    Y que los archivos criticos de esa fase existan en disco."""
    try:
        estado = state.leer(proyecto_id)
    except FileNotFoundError:
        return False

    fase_actual_idx = FASES_ORDEN.index(estado.fase_actual) if estado.fase_actual in FASES_ORDEN else -1
    fase_objetivo_idx = FASES_ORDEN.index(fase_objetivo)

    if fase_actual_idx <= fase_objetivo_idx:
        return False

    if fase_objetivo == "estrategia":
        return bool(estado.estrategia.titulo_ganador)

    if fase_objetivo == "guion":
        return estado.guion.aprobado

    if fase_objetivo == "visual":
        if not estado.visual.prompts_generados:
            return False
        rutas = estado.visual.imagenes + estado.visual.clips_video
        if not rutas:
            return False
        return all(_archivo_existe(r) for r in rutas)

    if fase_objetivo == "audio":
        if not _archivo_existe(estado.audio.voz_path):
            return False
        if estado.audio.subtitulos_path and not _archivo_existe(estado.audio.subtitulos_path):
            return False
        return True

    if fase_objetivo == "cierre":
        if not _archivo_existe(estado.video_final_path):
            return False
        return estado.compliance.aprobado is not None

    return False


@app.get("/health")
def health():
    return {"servicio": "orquestador_central", "estado": "ok"}


@app.post("/proyectos")
def crear_proyecto(proyecto_id: str, canal: str):
    try:
        return state.crear(proyecto_id, canal)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/proyectos/{proyecto_id}")
def leer_proyecto(proyecto_id: str):
    try:
        return state.leer(proyecto_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/proyectos")
def listar_proyectos():
    return {"proyectos": state.listar_proyectos()}


MAX_NICHO_LEN = 200
_NICHO_PERMITIDO = re.compile(r"^[\w\sáéíóúñüÁÉÍÓÚÑÜ\-,.\&/\(\)]+$")
_NICHO_PROHIBIDO = re.compile(r"[<>\{\}\"\';`\\|]")


@app.post("/pipeline/ejecutar")
def ejecutar_pipeline(proyecto_id: str, nicho: str, canal: str = "mi_canal", canal_id: str | None = None):
    """Corre el pipeline completo con tracking de fase, reintentos y recovery."""

    nicho = nicho.strip()
    if not nicho:
        raise HTTPException(status_code=422, detail="El parametro 'nicho' no puede estar vacio")
    if len(nicho) > MAX_NICHO_LEN:
        raise HTTPException(
            status_code=422,
            detail=f"El parametro 'nicho' excede {MAX_NICHO_LEN} caracteres ({len(nicho)})",
        )
    chars_prohibidos = _NICHO_PROHIBIDO.findall(nicho)
    if chars_prohibidos:
        raise HTTPException(
            status_code=422,
            detail=f"El parametro 'nicho' contiene caracteres no permitidos: {' '.join(set(chars_prohibidos))}",
        )

    log.info("pipeline inicio | proyecto=%s | nicho=%s | canal=%s | canal_id=%s", proyecto_id, nicho, canal, canal_id)
    event_store.registrar(
        "pipeline_started", "success",
        source="orquestador_central", proyecto_id=proyecto_id,
        data={"nicho": nicho, "canal": canal, "canal_id": canal_id},
    )
    pipeline_inicio = time.time()

    try:
        # 0. Crear proyecto si no existe
        try:
            state.leer(proyecto_id)
        except FileNotFoundError:
            state.crear(proyecto_id, canal)

        if canal_id:
            state.actualizar(proyecto_id, canal_id=canal_id)

        # 0.1 Validar TODAS las credenciales antes de gastar un solo segundo
        try:
            validar_todo()
        except HealthCheckError as exc:
            state.actualizar(
                proyecto_id,
                fase_actual="error",
                errores=[f"Pre-check: {f}" for f in exc.fallos],
            )
            raise HTTPException(status_code=422, detail=str(exc))

        # 0.5 Channel Intelligence (si canal_id proporcionado)
        if canal_id:
            try:
                validar_fase("inteligencia")
                _llamar("sub_orq_inteligencia", proyecto_id, {
                    "canal_id": canal_id,
                    "canal_input": canal_id,
                    "modo": "quick_refresh",
                })
                canal_data = channel_mgr.leer(canal_id)
                state.actualizar(proyecto_id, estrategia={
                    "canal_id": canal_id,
                    "contexto_canal": canal_data.perfil.model_dump(),
                    "competidores_contexto": [c.model_dump() for c in canal_data.competidores[:3]],
                    "tendencias_nicho": canal_data.tendencias_nicho,
                    "brechas_contenido": canal_data.brechas_contenido,
                })
                if canal_data.perfil.tono:
                    state.actualizar(proyecto_id, estrategia={"canal_tono": canal_data.perfil.tono})
            except Exception as exc:
                log.warning("channel intelligence fallo (no critico): %s", exc)

        # 1. Estrategia (Investigador -> Copywriter -> Director de Arte)
        if not _fase_completada(proyecto_id, "estrategia"):
            validar_fase("estrategia")
            _fase(proyecto_id, "estrategia")
            _llamar("sub_orq_estrategia", proyecto_id, {"nicho": nicho})

        # 2. Guion (Sub-orquestador maneja loop escritura/evaluacion/reescritura)
        if not _fase_completada(proyecto_id, "guion"):
            validar_fase("guion")
            _fase(proyecto_id, "guion")
            resultado_guion = _llamar("sub_orq_guion", proyecto_id)
            output = resultado_guion.get("output", {})
            if not output.get("aprobado"):
                state.actualizar(
                    proyecto_id,
                    fase_actual="error",
                    errores=["Guion no paso el score minimo tras varios intentos"],
                )
                raise HTTPException(
                    status_code=422,
                    detail="El guion no paso el score minimo tras varios intentos de reescritura",
                )

        # 3. Visual (Sub-orquestador maneja generacion + validacion de calidad)
        if not _fase_completada(proyecto_id, "visual"):
            validar_fase("visual")
            _fase(proyecto_id, "visual")
            _llamar("sub_orq_visual", proyecto_id)

        if not _fase_completada(proyecto_id, "audio"):
            validar_fase("audio")
            _fase(proyecto_id, "audio")
            _llamar("sub_orq_audio", proyecto_id)

        # 5. Cierre (Editor + SEO + Compliance + Publicador)
        if not _fase_completada(proyecto_id, "cierre"):
            validar_fase("cierre")
            _fase(proyecto_id, "cierre")
            _llamar("sub_orq_cierre", proyecto_id)

        state.actualizar(proyecto_id, fase_actual="completado", agente_actual=None)
        duracion_total = round(time.time() - pipeline_inicio, 2)
        log.info("pipeline completado | proyecto=%s | duracion_total=%.2fs", proyecto_id, duracion_total)
        event_store.registrar(
            "pipeline_completed", "success",
            source="orquestador_central", proyecto_id=proyecto_id,
            data={"nicho": nicho},
            duration_seg=duracion_total,
        )
        return state.leer(proyecto_id)

    except HTTPException:
        raise
    except HealthCheckError as exc:
        log.error("pipeline health check fallo | proyecto=%s | %s", proyecto_id, exc)
        event_store.registrar(
            "pipeline_failed", "error",
            source="orquestador_central", proyecto_id=proyecto_id,
            data={"error": str(exc), "fallos": exc.fallos},
            duration_seg=round(time.time() - pipeline_inicio, 2),
        )
        state.actualizar(
            proyecto_id,
            fase_actual="error",
            agente_actual=None,
            errores=[f"Pre-fase: {f}" for f in exc.fallos],
        )
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        log.error("pipeline error | proyecto=%s | %s", proyecto_id, exc, exc_info=True)
        event_store.registrar(
            "pipeline_failed", "error",
            source="orquestador_central", proyecto_id=proyecto_id,
            data={"error": str(exc)},
            duration_seg=round(time.time() - pipeline_inicio, 2),
        )
        state.actualizar(
            proyecto_id,
            fase_actual="error",
            agente_actual=None,
            errores=[str(exc)],
        )
        raise HTTPException(status_code=500, detail=str(exc))


# ── Performance Tracking (post-publicacion) ──────────────────

@app.post("/performance/checkpoint")
def ejecutar_checkpoint(proyecto_id: str, checkpoint: str):
    """
    Dispara un checkpoint de performance para un video ya publicado.

    checkpoint: t_24h | t_48h | t_72h | t_7d | t_30d
    """
    try:
        proyecto = state.leer(proyecto_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Proyecto {proyecto_id} no encontrado")

    if not proyecto.publicado or not proyecto.youtube_video_id:
        raise HTTPException(status_code=422, detail="El proyecto no ha sido publicado aun")

    canal_id = proyecto.canal_id or proyecto.estrategia.canal_id
    if not canal_id:
        raise HTTPException(status_code=422, detail="No hay canal_id asociado al proyecto")

    log.info("checkpoint %s | proyecto=%s | video=%s", checkpoint, proyecto_id, proyecto.youtube_video_id)

    resultado = _llamar("0.5_tracker_performance", proyecto_id, {
        "video_id": proyecto.youtube_video_id,
        "canal_id": canal_id,
        "checkpoint": checkpoint,
    })

    return resultado


@app.post("/performance/evaluar_pendientes")
def evaluar_pendientes():
    """
    Revisa todos los proyectos publicados y dispara checkpoints
    que correspondan segun el tiempo transcurrido desde la publicacion.
    Diseñado para ser llamado periodicamente (ej. cada 6 horas via n8n).
    """
    from shared.schemas import CHECKPOINT_HORAS

    proyectos = state.listar_proyectos()
    resultados = []

    for pid in proyectos:
        try:
            proyecto = state.leer(pid)
        except Exception:
            continue

        if not proyecto.publicado or not proyecto.youtube_video_id or not proyecto.publicado_en:
            continue

        horas_desde_pub = (datetime.utcnow() - proyecto.publicado_en).total_seconds() / 3600
        checkpoints_hechos = set()
        if proyecto.performance:
            checkpoints_hechos = {cp.tipo for cp in proyecto.performance.checkpoints}

        for tipo, horas_min in CHECKPOINT_HORAS.items():
            if tipo in checkpoints_hechos:
                continue
            if horas_desde_pub >= horas_min:
                try:
                    canal_id = proyecto.canal_id or proyecto.estrategia.canal_id
                    if not canal_id:
                        continue
                    _llamar("0.5_tracker_performance", pid, {
                        "video_id": proyecto.youtube_video_id,
                        "canal_id": canal_id,
                        "checkpoint": tipo.value,
                    })
                    resultados.append({"proyecto_id": pid, "checkpoint": tipo.value, "estado": "ok"})
                    log.info("auto-checkpoint %s | proyecto=%s", tipo.value, pid)
                except Exception as exc:
                    resultados.append({"proyecto_id": pid, "checkpoint": tipo.value, "estado": "error", "error": str(exc)})
                    log.warning("auto-checkpoint fallo %s | proyecto=%s | %s", tipo.value, pid, exc)
                break

    return {"evaluados": len(resultados), "resultados": resultados}


# ── Scheduling (endpoints para n8n) ───────────────────────────

@app.post("/scheduling/puede_generar")
def puede_generar(canal_id: str | None = None, frecuencia: str | None = None):
    """
    Verifica si se debe generar un nuevo video o si el buffer esta lleno.
    n8n llama esto ANTES de disparar /pipeline/ejecutar.

    Chequea:
      0. Pausa global: si la automatizacion esta pausada, no se puede generar
      1. Buffer: cuantos proyectos completados pero no publicados hay
      2. Frecuencia: si la frecuencia del canal permite generar hoy
      3. Ultimo generado: que no haya un pipeline corriendo ahora mismo

    Responde {puede: true/false, razon: "...", detalle: {...}}
    """
    from shared import scheduler
    from shared.config import BUFFER_MAX_VIDEOS

    # Check 0: pausa global
    if scheduler.esta_pausado():
        pausa = scheduler.obtener_pausa()
        return {
            "puede": False,
            "razon": f"Automatizacion pausada{': ' + pausa['razon'] if pausa.get('razon') else ''}",
            "detalle": {"pausado": True, "pausado_en": pausa.get("pausado_en"), "pausado_por": pausa.get("pausado_por")},
        }

    proyectos_ids = state.listar_proyectos()

    # Contar estados
    completados_sin_publicar = 0
    en_proceso = 0
    publicados = 0
    ultimo_creado = None

    for pid in proyectos_ids:
        try:
            proyecto = state.leer(pid)
        except Exception:
            continue

        if proyecto.publicado:
            publicados += 1
        elif proyecto.fase_actual == "completado":
            completados_sin_publicar += 1
        elif proyecto.fase_actual in ("estrategia", "guion", "visual", "audio", "cierre"):
            en_proceso += 1

        if ultimo_creado is None or proyecto.creado_en > ultimo_creado:
            ultimo_creado = proyecto.creado_en

    detalle = {
        "buffer_actual": completados_sin_publicar,
        "buffer_max": BUFFER_MAX_VIDEOS,
        "en_proceso": en_proceso,
        "publicados": publicados,
        "total_proyectos": len(proyectos_ids),
    }

    # Check 1: hay un pipeline corriendo ahora?
    if en_proceso > 0:
        return {"puede": False, "razon": f"Hay {en_proceso} pipeline(s) en proceso", "detalle": detalle}

    # Check 2: buffer lleno?
    if completados_sin_publicar >= BUFFER_MAX_VIDEOS:
        return {
            "puede": False,
            "razon": f"Buffer lleno: {completados_sin_publicar}/{BUFFER_MAX_VIDEOS} videos esperando publicacion",
            "detalle": detalle,
        }

    # Check 3: frecuencia (query param override > PerfilCanal)
    freq = frecuencia
    if not freq and canal_id:
        try:
            canal = channel_mgr.leer(canal_id)
            freq = canal.perfil.frecuencia_publicacion
        except FileNotFoundError:
            pass

    if freq and ultimo_creado:
        horas_desde_ultimo = (datetime.utcnow() - ultimo_creado).total_seconds() / 3600
        horas_minimas = _frecuencia_a_horas(freq)
        if horas_desde_ultimo < horas_minimas:
            horas_falta = round(horas_minimas - horas_desde_ultimo, 1)
            detalle["frecuencia"] = freq
            detalle["horas_desde_ultimo"] = round(horas_desde_ultimo, 1)
            detalle["horas_minimas"] = horas_minimas
            return {
                "puede": False,
                "razon": f"Frecuencia '{freq}': faltan {horas_falta}h para el proximo video",
                "detalle": detalle,
            }

    return {"puede": True, "razon": "Buffer disponible, listo para generar", "detalle": detalle}


def _frecuencia_a_horas(frecuencia: str) -> float:
    """Convierte la frecuencia textual del canal a horas minimas entre videos."""
    mapping = {
        "diario": 20,
        "daily": 20,
        "cada 2 dias": 44,
        "every 2 days": 44,
        "3 por semana": 48,
        "3 per week": 48,
        "semanal": 144,
        "weekly": 144,
        "quincenal": 312,
        "biweekly": 312,
    }
    return mapping.get(frecuencia.lower().strip(), 20)


@app.get("/scheduling/health_servicios")
def health_servicios():
    """
    Hace ping a /health de todos los servicios registrados en paralelo.
    Responde con lista de vivos/muertos y un score general.
    Diseñado para que n8n lo llame ANTES de lanzar un pipeline.
    """
    import concurrent.futures

    resultados = {}
    agentes = list(REGISTRO_AGENTES.items())

    def ping_servicio(agente_id: str, puerto: int) -> dict:
        try:
            resp = httpx.get(f"http://localhost:{puerto}/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "estado": "ok",
                    "puerto": puerto,
                    "memoria_mb": data.get("memoria_mb"),
                    "uptime_seg": data.get("uptime_seg"),
                }
            return {"estado": "error", "puerto": puerto, "status_code": resp.status_code}
        except Exception as e:
            return {"estado": "caido", "puerto": puerto, "error": str(e)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(ping_servicio, aid, puerto): aid
            for aid, puerto in agentes
        }
        for future in concurrent.futures.as_completed(futures):
            agente_id = futures[future]
            resultados[agente_id] = future.result()

    vivos = sum(1 for r in resultados.values() if r["estado"] == "ok")
    total = len(resultados)
    score = round((vivos / total) * 100) if total > 0 else 0

    # Servicios criticos que DEBEN estar vivos para un pipeline
    criticos = [
        "orquestador_central", "sub_orq_estrategia", "sub_orq_guion",
        "sub_orq_visual", "sub_orq_audio", "sub_orq_cierre",
        "1.1_investigador", "1.2_copywriter", "2.1_guionista",
        "3.2_generador_visual", "4.1_locucion", "5.1_editor",
    ]
    criticos_caidos = [
        aid for aid in criticos
        if resultados.get(aid, {}).get("estado") != "ok"
    ]

    puede_pipeline = len(criticos_caidos) == 0

    if score >= 90:
        nivel = "saludable"
    elif score >= 60:
        nivel = "degradado"
    else:
        nivel = "critico"

    # Desglose por departamento
    deptos = {
        "depto_0_inteligencia": ["0.1_escaner_canal", "0.2_analizador_canal", "0.3_monitor_mercado", "0.4_asesor_estrategico", "0.5_tracker_performance", "sub_orq_inteligencia"],
        "depto_1_estrategia": ["1.1_investigador", "1.2_copywriter", "1.3_director_arte", "1.4_generador_miniatura", "sub_orq_estrategia"],
        "depto_2_guion": ["2.1_guionista", "sub_orq_guion"],
        "depto_3_visual": ["3.1_prompt_maker", "3.2_generador_visual", "sub_orq_visual"],
        "depto_4_audio": ["4.1_locucion", "4.2_musica", "4.3_subtitulos", "sub_orq_audio"],
        "depto_5_cierre": ["5.1_editor", "5.2_seo", "5.3_compliance", "5.4_policy_monitor", "5.5_publicador", "sub_orq_cierre"],
        "orquestador": ["orquestador_central"],
    }
    desglose = {}
    for depto, agentes_depto in deptos.items():
        vivos_depto = sum(1 for a in agentes_depto if resultados.get(a, {}).get("estado") == "ok")
        desglose[depto] = {"vivos": vivos_depto, "total": len(agentes_depto)}

    memorias = [r.get("memoria_mb") for r in resultados.values() if r.get("memoria_mb")]
    memoria_total_mb = round(sum(memorias), 1) if memorias else None

    return {
        "score": score,
        "nivel": nivel,
        "vivos": vivos,
        "total": total,
        "memoria_total_mb": memoria_total_mb,
        "puede_pipeline": puede_pipeline,
        "criticos_caidos": criticos_caidos,
        "desglose_departamentos": desglose,
        "servicios": resultados,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES["orquestador_central"])
