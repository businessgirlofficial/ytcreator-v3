"""
Cliente API - YTCreator Studio v3
====================================

Encapsula las llamadas HTTP al gateway/agentes para que Streamlit
no tenga que conocer puertos ni endpoints internos.

Usa GATEWAY_URL (default http://localhost:7861) para conectarse.
Si el gateway no esta disponible, las funciones lanzan excepciones
claras que el UI puede mostrar al usuario.
"""

import os
import uuid

import httpx
from dotenv import load_dotenv

load_dotenv()

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:7861")
API_KEY = os.getenv("YTCREATOR_API_KEY", "")
TIMEOUT_CORTO = 30
TIMEOUT_AGENTE = 300
TIMEOUT_PIPELINE = 600


def _headers() -> dict:
    if API_KEY:
        return {"X-API-Key": API_KEY}
    return {}


def _post(path: str, timeout: int = TIMEOUT_CORTO, **kwargs) -> dict:
    headers = _headers()
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    resp = httpx.post(f"{GATEWAY_URL}{path}", headers=headers, timeout=timeout, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _get(path: str, timeout: int = TIMEOUT_CORTO) -> dict:
    resp = httpx.get(f"{GATEWAY_URL}{path}", headers=_headers(), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def health() -> bool:
    try:
        data = _get("/health")
        return data.get("estado") == "ok"
    except Exception:
        return False


def crear_proyecto(proyecto_id: str, canal: str = "MiCanal") -> dict:
    return _post("/proyectos", params={"proyecto_id": proyecto_id, "canal": canal})


def estado_proyecto(proyecto_id: str) -> dict:
    return _get(f"/proyectos/{proyecto_id}")


def listar_proyectos() -> list[str]:
    data = _get("/proyectos")
    return data.get("proyectos", [])


def ejecutar_agente(agente_id: str, proyecto_id: str, parametros: dict | None = None) -> dict:
    request = {"proyecto_id": proyecto_id, "parametros": parametros or {}}
    return _post(f"/agentes/{agente_id}/ejecutar", json=request, timeout=TIMEOUT_AGENTE)


def ejecutar_pipeline(proyecto_id: str, nicho: str, canal_id: str | None = None) -> dict:
    params = {"proyecto_id": proyecto_id, "nicho": nicho}
    if canal_id:
        params["canal_id"] = canal_id
    return _post(
        "/pipeline/ejecutar",
        params=params,
        timeout=TIMEOUT_PIPELINE,
    )


def pipeline_estado(proyecto_id: str) -> dict:
    return _get(f"/pipeline/estado/{proyecto_id}")


def webhook_trigger(nicho: str, canal: str = "MiCanal", canal_id: str | None = None, callback_url: str | None = None) -> dict:
    payload = {"nicho": nicho, "canal": canal}
    if canal_id:
        payload["canal_id"] = canal_id
    if callback_url:
        payload["callback_url"] = callback_url
    return _post("/pipeline/webhook", json=payload)


# ── Funciones de conveniencia para cada departamento ────────────

def analizar_nicho(proyecto_id: str, nicho: str) -> dict:
    resultado = ejecutar_agente("1.1_investigador", proyecto_id, {"nicho": nicho})
    return resultado.get("output", {})


def generar_titulos(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("1.2_copywriter", proyecto_id)
    return resultado.get("output", {})


def generar_miniatura(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("1.3_director_arte", proyecto_id)
    return resultado.get("output", {})


def generar_guion(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("2.1_guionista", proyecto_id)
    return resultado.get("output", {})


def evaluar_guion(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("sub_orq_guion", proyecto_id)
    return resultado.get("output", {})


def generar_prompts_visuales(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("3.1_prompt_maker", proyecto_id)
    return resultado.get("output", {})


def lanzar_generacion_visual(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("3.2_generador_visual", proyecto_id)
    return resultado.get("output", {})


def generar_locucion(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("4.1_locucion", proyecto_id)
    return resultado.get("output", {})


def generar_musica(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("4.2_musica", proyecto_id)
    return resultado.get("output", {})


def generar_subtitulos(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("4.3_subtitulos", proyecto_id)
    return resultado.get("output", {})


def ensamblar_video(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("5.1_editor", proyecto_id)
    return resultado.get("output", {})


def generar_seo(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("5.2_seo", proyecto_id)
    return resultado.get("output", {})


def verificar_compliance(proyecto_id: str) -> dict:
    resultado = ejecutar_agente("5.3_compliance", proyecto_id)
    return resultado.get("output", {})


def verificar_politicas() -> dict:
    resultado = ejecutar_agente("5.4_policy_monitor", "system", {})
    return resultado.get("output", {})


# ── Channel Intelligence ─────────────────────────────────────────


def conectar_canal(canal_input: str) -> dict:
    return _post("/canales/conectar", json={"canal_input": canal_input}, timeout=TIMEOUT_AGENTE)


def listar_canales() -> list[dict]:
    data = _get("/canales")
    return data.get("canales", [])


def estado_canal(canal_id: str) -> dict:
    return _get(f"/canales/{canal_id}")


def refrescar_canal(canal_id: str) -> dict:
    return _post(f"/canales/{canal_id}/refrescar", timeout=TIMEOUT_AGENTE)


def eliminar_canal(canal_id: str) -> dict:
    resp = httpx.delete(f"{GATEWAY_URL}/canales/{canal_id}", headers=_headers(), timeout=TIMEOUT_CORTO)
    resp.raise_for_status()
    return resp.json()


def agregar_competidor(canal_id: str, competidor_input: str) -> dict:
    return _post(
        f"/canales/{canal_id}/competidores",
        json={"competidor_input": competidor_input},
        timeout=TIMEOUT_AGENTE,
    )


def eliminar_competidor(canal_id: str, comp_id: str) -> dict:
    resp = httpx.delete(f"{GATEWAY_URL}/canales/{canal_id}/competidores/{comp_id}", headers=_headers(), timeout=TIMEOUT_CORTO)
    resp.raise_for_status()
    return resp.json()


def obtener_ideas(canal_id: str) -> list[dict]:
    data = _get(f"/canales/{canal_id}/ideas")
    return data.get("ideas", [])


def refrescar_ideas(canal_id: str) -> list[dict]:
    data = _post(f"/canales/{canal_id}/ideas/refrescar", timeout=TIMEOUT_AGENTE)
    return data.get("ideas", [])


def quota_hoy() -> dict:
    return _get("/quota/hoy")


def get_identidad_visual(canal_id: str) -> dict:
    return _get(f"/canales/{canal_id}/identidad-visual")


def set_identidad_visual(canal_id: str, payload: dict) -> dict:
    return _post(f"/canales/{canal_id}/identidad-visual", json=payload)


def get_estilos(categoria: str | None = None) -> dict:
    params = f"?categoria={categoria}" if categoria else ""
    return _get(f"/estilos{params}")


def health_servicios() -> dict:
    return _get("/scheduling/health_servicios", timeout=30)


def pipeline_cola() -> dict:
    return _get("/pipeline/cola", timeout=30)


def listar_proyectos_detalle() -> list[dict]:
    ids = listar_proyectos()
    proyectos = []
    for pid in ids:
        try:
            proyectos.append(pipeline_estado(pid))
        except Exception:
            proyectos.append({"proyecto_id": pid, "fase_actual": "desconocido", "errores": []})
    return proyectos


def sync_state_to_session(proyecto_id: str) -> dict:
    """Convierte EstadoProyecto del API al formato de session state de Streamlit."""
    estado = estado_proyecto(proyecto_id)

    estrategia = estado.get("estrategia", {})
    guion = estado.get("guion", {})
    visual = estado.get("visual", {})
    audio = estado.get("audio", {})
    metadata = estado.get("metadata", {})

    session = {
        "nicho": estrategia.get("nicho", ""),
        "nicho_analizado": bool(estrategia.get("patrones_virales")),
        "analisis_nicho": {
            "nicho": estrategia.get("nicho", ""),
            "analisis": {"tipo_audiencia": "", "mejor_formato": "", "duracion_ideal": ""},
            "triggers_emocionales": [],
            "palabras_power": [],
            "frameworks_titulo": [],
            "patrones_virales": estrategia.get("patrones_virales", []),
        } if estrategia.get("patrones_virales") else None,
        "titulos_generados": [
            {"titulo": t, "framework_usado": "", "trigger": "", "por_que_funciona": "",
             "potencial_viral": "alto", "ctr_estimado": "—"}
            for t in estrategia.get("titulos_candidatos", [])
        ] if estrategia.get("titulos_candidatos") else None,
        "titulo_elegido": estrategia.get("titulo_ganador", ""),
        "guion_aprobado": {
            "titulo": estrategia.get("titulo_ganador", ""),
            "escenas": [
                {"numero": e.get("numero", i+1), "narracion": e.get("texto", ""),
                 "descripcion_visual": e.get("prompt_visual", "")}
                for i, e in enumerate(guion.get("escenas", []))
            ],
            "tags": metadata.get("tags", []),
            "descripcion_youtube": metadata.get("descripcion", ""),
        } if guion.get("aprobado") else None,
        "guion_texto_completo": guion.get("texto_completo"),
        "audio_generado": audio.get("voz_path") is not None,
        "musica_lista": audio.get("musica_path") is not None,
        "subs_generados": audio.get("subtitulos_path") is not None,
        "kaggle_completado": visual.get("prompts_generados", False),
        "video_final": estado.get("video_final_path"),
    }

    return session


# ── Eventos de automatización ─────────────────────────────────────


def listar_eventos(
    limit: int = 100,
    event_type: str | None = None,
    status: str | None = None,
    proyecto_id: str | None = None,
    source: str | None = None,
    desde: str | None = None,
) -> list[dict]:
    params = f"?limit={limit}"
    if event_type:
        params += f"&event_type={event_type}"
    if status:
        params += f"&status={status}"
    if proyecto_id:
        params += f"&proyecto_id={proyecto_id}"
    if source:
        params += f"&source={source}"
    if desde:
        params += f"&desde={desde}"
    data = _get(f"/eventos{params}")
    return data.get("eventos", [])


def eventos_stats() -> dict:
    return _get("/eventos/stats")


# ── Scheduler (tareas programadas) ────────────────────────────────


def scheduler_resumen() -> dict:
    return _get("/scheduler")


def scheduler_tareas() -> list[dict]:
    data = _get("/scheduler/tareas")
    return data.get("tareas", [])


def scheduler_toggle(task_id: str, habilitado: bool) -> dict:
    return _post(f"/scheduler/tareas/{task_id}/toggle", params={"habilitado": str(habilitado).lower()})


def scheduler_pausa() -> dict:
    return _get("/scheduler/pausa")


def scheduler_pausar(razon: str | None = None) -> dict:
    params = {}
    if razon:
        params["razon"] = razon
    return _post("/scheduler/pausar", params=params)


def scheduler_reanudar() -> dict:
    return _post("/scheduler/reanudar")


# ── Keyword Performance Tracking ─────────────────────────────────


def keywords_top(limit: int = 30, ordenar_por: str = "vistas_promedio", min_usos: int = 1) -> list[dict]:
    data = _get(f"/keywords/top?limit={limit}&ordenar_por={ordenar_por}&min_usos={min_usos}")
    return data.get("keywords", [])


def keyword_historial(keyword: str, limit: int = 20) -> list[dict]:
    data = _get(f"/keywords/{keyword}/historial?limit={limit}")
    return data.get("historial", [])


def keywords_stats() -> dict:
    return _get("/keywords/stats")
