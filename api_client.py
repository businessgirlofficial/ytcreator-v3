"""
Cliente API - YTCreator Studio v3
====================================

Encapsula las llamadas HTTP al gateway/agentes para que Streamlit
no tenga que conocer puertos ni endpoints internos.

Usa GATEWAY_URL (default http://localhost:7860) para conectarse.
Si el gateway no esta disponible, las funciones lanzan excepciones
claras que el UI puede mostrar al usuario.
"""

import os
import uuid

import httpx
from dotenv import load_dotenv

load_dotenv()

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:7860")
TIMEOUT_CORTO = 30
TIMEOUT_AGENTE = 300
TIMEOUT_PIPELINE = 600


def _post(path: str, timeout: int = TIMEOUT_CORTO, **kwargs) -> dict:
    resp = httpx.post(f"{GATEWAY_URL}{path}", timeout=timeout, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _get(path: str, timeout: int = TIMEOUT_CORTO) -> dict:
    resp = httpx.get(f"{GATEWAY_URL}{path}", timeout=timeout)
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


def ejecutar_pipeline(proyecto_id: str, nicho: str) -> dict:
    return _post(
        "/pipeline/ejecutar",
        params={"proyecto_id": proyecto_id, "nicho": nicho},
        timeout=TIMEOUT_PIPELINE,
    )


def pipeline_estado(proyecto_id: str) -> dict:
    return _get(f"/pipeline/estado/{proyecto_id}")


def webhook_trigger(nicho: str, canal: str = "MiCanal", callback_url: str | None = None) -> dict:
    payload = {"nicho": nicho, "canal": canal}
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
    resultado = ejecutar_agente("2.2_evaluador", proyecto_id)
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
