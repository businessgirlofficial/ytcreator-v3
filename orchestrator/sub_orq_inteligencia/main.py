"""
Sub-orquestador - Depto 0 (Inteligencia de Canal)

Tres modos de operacion:

  Modo A (escaneo completo):
    0.1 Escaner -> 0.2 Analizador -> 0.3 Monitor Mercado -> 0.4 Asesor
    Si no hay cronograma activo o esta por agotarse, agrega:
    -> 0.6 Planificador (genera cronograma automaticamente)

  Modo B (quick refresh):
    Si los datos del canal tienen < 24h, solo re-ejecuta 0.4 (Asesor).
    Si estan viejos, ejecuta Modo A completo.

  Modo C (pre-produccion):
    Refresca datos si estan viejos -> ejecuta revision de vigencia
    (0.6 modo revisar) para la entrada del cronograma que se va a producir.

  Modo D (adaptar cronograma):
    Enruta senales de performance del tracker (0.5) al planificador
    (0.6 modo adaptar) para inyectar follow-ups o flagear entradas.
"""

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.channel_manager import ChannelManager
from shared.config import REGISTRO_AGENTES
from shared.http_client import llamar_con_reintento
from shared.logger import get_logger
from shared.schemas import AgenteRequest, AgenteResponse

AGENTE_ID = "sub_orq_inteligencia"
app: FastAPI = crear_agente_app(
    AGENTE_ID,
    descripcion="Orquesta el pipeline de inteligencia de canal",
)
channels = ChannelManager()
log = get_logger(AGENTE_ID)

SECUENCIA_COMPLETA = [
    "0.1_escaner_canal",
    "0.2_analizador_canal",
    "0.3_monitor_mercado",
    "0.4_asesor_estrategico",
]

UMBRAL_REGENERACION = 3


# ── Helpers ───────────────────────────────────────────────────

def _necesita_cronograma(canal_id: str) -> bool:
    """Verifica si el canal necesita un cronograma nuevo."""
    try:
        estado = channels.leer(canal_id)
        if not estado.cronograma_activo:
            return True

        cron = estado.cronograma_activo
        if cron.status in ("completado", "reemplazado", "cancelado"):
            return True

        pendientes = sum(
            1 for e in cron.entradas
            if e.status in ("pendiente", "en_revision", "aprobado")
        )
        return pendientes <= UMBRAL_REGENERACION
    except Exception:
        return False


def _ejecutar_planificador(proyecto_id: str, parametros: dict, timeout: int = 300) -> dict:
    req = AgenteRequest(proyecto_id=proyecto_id, parametros=parametros)
    return llamar_con_reintento("0.6_planificador_contenido", req, timeout=timeout)


# ── Modo A: Escaneo completo ─────────────────────────────────

def _escaneo_completo(request: AgenteRequest, canal_id: str, canal_input: str) -> dict:
    resultados = {}

    req_escaner = AgenteRequest(
        proyecto_id=request.proyecto_id,
        parametros={"canal_input": canal_input or canal_id},
    )
    data_escaner = llamar_con_reintento(
        "0.1_escaner_canal", req_escaner, timeout=120,
    )
    resultados["0.1_escaner_canal"] = data_escaner

    canal_id_resuelto = (
        data_escaner.get("output", {}).get("canal_id") or canal_id
    )

    for agente_id in SECUENCIA_COMPLETA[1:]:
        req = AgenteRequest(
            proyecto_id=request.proyecto_id,
            parametros={"canal_id": canal_id_resuelto},
        )
        data = llamar_con_reintento(agente_id, req, timeout=120)
        resultados[agente_id] = data

    # ── Generar cronograma si no hay uno activo o esta por agotarse ──
    cronograma_generado = False
    if _necesita_cronograma(canal_id_resuelto):
        log.info(
            "canal %s necesita cronograma, generando...", canal_id_resuelto,
        )
        try:
            data_cron = _ejecutar_planificador(request.proyecto_id, {
                "canal_id": canal_id_resuelto,
                "modo": "generar",
                "periodo_dias": 30,
                "frecuencia_semanal": 4,
            })
            resultados["0.6_planificador_contenido"] = data_cron
            cronograma_generado = True
            log.info("cronograma generado para canal %s", canal_id_resuelto)
        except Exception as exc:
            log.warning("error generando cronograma (no critico): %s", exc)
            resultados["0.6_planificador_contenido"] = {"error": str(exc)}

    return {
        "modo": "completo",
        "canal_id": canal_id_resuelto,
        "cronograma_generado": cronograma_generado,
        "resultados": resultados,
    }


# ── Modo B: Quick refresh ────────────────────────────────────

def _quick_refresh(request: AgenteRequest, canal_id: str) -> dict:
    necesita_refresco = channels.canal_necesita_refresco(canal_id)
    if necesita_refresco:
        log.info("canal %s necesita refresco completo", canal_id)
        return _escaneo_completo(request, canal_id, canal_id)

    log.info("canal %s esta fresco, solo re-ejecutando asesor", canal_id)
    req_asesor = AgenteRequest(
        proyecto_id=request.proyecto_id,
        parametros={"canal_id": canal_id},
    )
    data = llamar_con_reintento(
        "0.4_asesor_estrategico", req_asesor, timeout=120,
    )
    return {"modo": "quick_refresh", "asesor": data, "canal_id": canal_id}


# ── Modo C: Pre-produccion ───────────────────────────────────

def _pre_produccion(request: AgenteRequest, canal_id: str, dia: int) -> dict:
    """Refresca datos si estan viejos y ejecuta revision de vigencia."""
    resultados = {}

    # 1. Refrescar datos si tienen mas de 24h
    necesita_refresco = channels.canal_necesita_refresco(canal_id)
    if necesita_refresco:
        log.info(
            "pre-produccion: datos viejos para %s, refrescando...", canal_id,
        )
        try:
            for agente_id in ["0.3_monitor_mercado", "0.4_asesor_estrategico"]:
                req = AgenteRequest(
                    proyecto_id=request.proyecto_id,
                    parametros={"canal_id": canal_id},
                )
                data = llamar_con_reintento(agente_id, req, timeout=120)
                resultados[agente_id] = data
        except Exception as exc:
            log.warning("refresco pre-produccion parcial: %s", exc)
    else:
        log.info("pre-produccion: datos frescos para %s", canal_id)

    # 2. Ejecutar revision de vigencia para la entrada
    log.info("pre-produccion: revisando vigencia dia %d | canal=%s", dia, canal_id)
    try:
        data_revision = _ejecutar_planificador(request.proyecto_id, {
            "canal_id": canal_id,
            "modo": "revisar",
            "dia": dia,
        })
        resultados["0.6_revision_vigencia"] = data_revision

        output = data_revision.get("output", {})
        decision = output.get("decision", "proceder")
        score = output.get("score_vigencia")
        titulo = output.get("titulo_final", "?")

        log.info(
            "pre-produccion: vigencia dia %d -> %s (score=%s) | titulo='%s'",
            dia, decision, score, titulo,
        )
    except Exception as exc:
        log.warning("revision de vigencia fallo (no critico): %s", exc)
        resultados["0.6_revision_vigencia"] = {"error": str(exc)}
        decision = "proceder"
        score = None
        titulo = "?"

    return {
        "modo": "pre_produccion",
        "canal_id": canal_id,
        "dia": dia,
        "datos_refrescados": necesita_refresco,
        "decision_vigencia": decision,
        "score_vigencia": score,
        "titulo_aprobado": titulo,
        "resultados": resultados,
    }


# ── Modo D: Adaptar cronograma ───────────────────────────────

def _adaptar_cronograma(request: AgenteRequest, canal_id: str, senal: dict) -> dict:
    """Enruta senales de performance al planificador para adaptar el cronograma."""
    log.info(
        "adaptando cronograma | canal=%s | senal=%s | video=%s",
        canal_id,
        senal.get("tipo_senal", "?"),
        senal.get("video_titulo", "?"),
    )

    try:
        data = _ejecutar_planificador(request.proyecto_id, {
            "canal_id": canal_id,
            "modo": "adaptar",
            "senal": senal,
        })

        output = data.get("output", {})
        accion = output.get("accion", "?")

        log.info(
            "cronograma adaptado | canal=%s | accion=%s", canal_id, accion,
        )

        return {
            "modo": "adaptar_cronograma",
            "canal_id": canal_id,
            "senal_tipo": senal.get("tipo_senal"),
            "accion": accion,
            "resultado": output,
        }
    except Exception as exc:
        log.warning("adaptacion de cronograma fallo: %s", exc)
        return {
            "modo": "adaptar_cronograma",
            "canal_id": canal_id,
            "senal_tipo": senal.get("tipo_senal"),
            "accion": "error",
            "error": str(exc),
        }


# ── Router principal ─────────────────────────────────────────

def logica(request: AgenteRequest) -> dict:
    canal_id = request.parametros.get("canal_id", "")
    canal_input = request.parametros.get("canal_input", "")
    modo = request.parametros.get("modo", "completo")

    if not canal_id and not canal_input:
        raise ValueError("Falta 'canal_id' o 'canal_input' en parametros")

    if modo == "quick_refresh" and canal_id:
        return _quick_refresh(request, canal_id)

    elif modo == "pre_produccion":
        if not canal_id:
            raise ValueError("Falta 'canal_id' para modo pre_produccion")
        dia = request.parametros.get("dia")
        if dia is None:
            raise ValueError("Falta 'dia' para modo pre_produccion")
        return _pre_produccion(request, canal_id, int(dia))

    elif modo == "adaptar_cronograma":
        if not canal_id:
            raise ValueError("Falta 'canal_id' para modo adaptar_cronograma")
        senal = request.parametros.get("senal")
        if not senal:
            raise ValueError("Falta 'senal' para modo adaptar_cronograma")
        return _adaptar_cronograma(request, canal_id, senal)

    else:
        return _escaneo_completo(request, canal_id, canal_input)


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
