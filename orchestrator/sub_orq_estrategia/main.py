"""
Sub-orquestador - Depto 1 (Estrategia)

Coordina, en orden: Investigador (1.1) -> Copywriter (1.2) -> Director
de Arte (1.3) -> Generador Miniatura (1.4).

Soporta dos modos de operacion:

  Modo LIBRE (sin cronograma):
    Funciona como siempre. Cada agente explora desde cero.

  Modo DIRIGIDO (con cronograma):
    Detecta que el proyecto tiene ContextoCronograma y pasa el contexto
    pre-calculado (titulo base, tema, angulo, keywords, formato) a cada
    agente via parametros. Los agentes refinan en vez de explorar.
    Al terminar, registra el titulo ganador en el cronograma para
    trazabilidad plan vs ejecucion.
"""

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
from shared.state_manager import StateManager

AGENTE_ID = "sub_orq_estrategia"
app: FastAPI = crear_agente_app(
    AGENTE_ID,
    descripcion="Orquesta Investigador, Copywriter y Director de Arte",
)
state = StateManager()
channels = ChannelManager()
log = get_logger(AGENTE_ID)

SECUENCIA = [
    "1.1_investigador",
    "1.2_copywriter",
    "1.3_director_arte",
    "1.4_generador_miniatura",
]


def _extraer_contexto_cronograma(proyecto_id: str) -> dict | None:
    try:
        proyecto = state.leer(proyecto_id)
        if not proyecto.modo_dirigido:
            return None

        c = proyecto.cronograma
        return {
            "cronograma_id": c.cronograma_id,
            "entrada_dia": c.entrada_dia,
            "titulo_sugerido": c.titulo_sugerido,
            "tema": c.tema,
            "angulo": c.angulo,
            "tipo_contenido": c.tipo_contenido,
            "formato": c.formato,
            "duracion_sugerida_min": c.duracion_sugerida_min,
            "keywords_recomendadas": c.keywords_recomendadas,
            "datos_soporte": c.datos_soporte,
            "potencial_viral": c.potencial_viral,
            "razon_tema": c.razon_tema,
            "decision_vigencia": c.decision_vigencia,
            "score_vigencia": c.score_vigencia,
        }
    except Exception as exc:
        log.warning("no se pudo extraer contexto cronograma: %s", exc)
        return None


def _inyectar_contexto_en_request(
    request: AgenteRequest,
    contexto: dict,
    agente_id: str,
) -> AgenteRequest:
    params = dict(request.parametros)
    params["entrada_cronograma"] = contexto

    if agente_id == "1.1_investigador":
        if not params.get("nicho"):
            params["nicho"] = contexto.get("tema") or contexto.get("titulo_sugerido", "")

    elif agente_id == "1.2_copywriter":
        params["titulo_base_cronograma"] = contexto.get("titulo_sugerido", "")
        params["angulo_cronograma"] = contexto.get("angulo", "")
        params["formato_cronograma"] = contexto.get("formato", "")
        params["keywords_cronograma"] = contexto.get("keywords_recomendadas", [])

    elif agente_id == "1.3_director_arte":
        params["tipo_contenido_cronograma"] = contexto.get("tipo_contenido", "")
        params["formato_cronograma"] = contexto.get("formato", "")
        params["datos_soporte_cronograma"] = contexto.get("datos_soporte", {})

    elif agente_id == "1.4_generador_miniatura":
        params["tipo_contenido_cronograma"] = contexto.get("tipo_contenido", "")

    return AgenteRequest(
        proyecto_id=request.proyecto_id,
        parametros=params,
    )


def _registrar_titulo_en_cronograma(
    proyecto_id: str,
    contexto: dict,
):
    try:
        proyecto = state.leer(proyecto_id)
        titulo_ganador = proyecto.estrategia.titulo_ganador
        if not titulo_ganador:
            return

        canal_id = proyecto.canal_id or proyecto.estrategia.canal_id
        if not canal_id:
            return

        canal = channels.leer(canal_id)
        if not canal.cronograma_activo:
            return

        cronograma = canal.cronograma_activo
        dia = contexto.get("entrada_dia")
        if dia is None:
            return

        for i, e in enumerate(cronograma.entradas):
            if e.dia == dia:
                titulo_original = e.titulo_sugerido
                if titulo_ganador != titulo_original:
                    cronograma.entradas[i].ajustes_historial.append({
                        "decision": "titulo_refinado_por_estrategia",
                        "titulo_cronograma": titulo_original,
                        "titulo_ganador": titulo_ganador,
                        "score": proyecto.estrategia.titulo_score,
                    })
                log.info(
                    "titulo registrado en cronograma | dia=%d | plan='%s' | final='%s'",
                    dia, titulo_original, titulo_ganador,
                )
                break

        import json
        channels.actualizar(
            canal_id,
            cronograma_activo=json.loads(cronograma.model_dump_json()),
        )
    except Exception as exc:
        log.warning("error registrando titulo en cronograma: %s", exc)


def logica(request: AgenteRequest) -> dict:
    contexto = _extraer_contexto_cronograma(request.proyecto_id)
    modo = "dirigido" if contexto else "libre"

    log.info(
        "estrategia inicio | proyecto=%s | modo=%s%s",
        request.proyecto_id,
        modo,
        f" | dia={contexto['entrada_dia']} | titulo_base='{contexto['titulo_sugerido']}'"
        if contexto else "",
    )

    resultados = {}
    for agente_id in SECUENCIA:
        if contexto:
            req = _inyectar_contexto_en_request(request, contexto, agente_id)
        else:
            req = request

        data = llamar_con_reintento(agente_id, req, timeout=120)
        resultados[agente_id] = data

    if contexto:
        _registrar_titulo_en_cronograma(request.proyecto_id, contexto)

    log.info(
        "estrategia completada | proyecto=%s | modo=%s",
        request.proyecto_id, modo,
    )

    return {
        "modo": modo,
        "resultados": resultados,
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
