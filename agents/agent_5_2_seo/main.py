"""
Agente 5.2 - Consultor SEO
Depto 5 (Cierre)

FASE 5 - IMPLEMENTACION REAL
================================
Groq genera la descripcion, los tags, la categoria y un titulo corto
por escena. El CODIGO convierte esos titulos de escena en capitulos
con timestamps reales, usando la MISMA division proporcional por
palabras que uso el Agente 5.1 (Editor) para construir el video --
viven juntas en shared/video_utils.py para que nunca queden
desincronizados.

Requiere que el Agente 5.1 (Editor) ya haya corrido: necesitamos la
duracion real del video final para que los timestamps de los
capitulos sean correctos.

El codigo tambien aplica la regla de YouTube de que los capitulos
deben estar separados por al menos 10 segundos -- si dos escenas
quedan mas juntas que eso, se descarta el capitulo mas tardio en vez
de generar capitulos invalidos.
"""

import sys
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
from shared.state_manager import StateManager
from shared.video_utils import calcular_duraciones_por_palabras

AGENTE_ID = "5.2_seo"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Genera descripcion, tags, categoria y capitulos con Groq")
state = StateManager()
channels = ChannelManager()

SEPARACION_MINIMA_CAPITULOS_SEG = 10  # requisito real de YouTube
YOUTUBE_MAX_TAG_CHARS = 500

import datetime as _dt


def _priorizar_tags(tags_raw: list[str], nicho: str, titulo: str, keywords: list[str]) -> list[str]:
    """Puntua, ordena y recorta tags al limite de 500 caracteres de YouTube."""
    nicho_lower = nicho.lower() if nicho else ""
    titulo_lower = titulo.lower() if titulo else ""
    keywords_lower = {k.lower() for k in keywords} if keywords else set()
    anio = str(_dt.date.today().year)

    scored = []
    vistos = set()
    for tag in tags_raw:
        tag = tag.strip()
        if not tag:
            continue
        tag_key = tag.lower()
        if tag_key in vistos:
            continue
        vistos.add(tag_key)

        score = 0
        if tag_key in keywords_lower:
            score += 10
        if any(k in tag_key for k in keywords_lower):
            score += 5
        if nicho_lower and nicho_lower in tag_key:
            score += 3
        if len(tag.split()) >= 3:
            score += 2
        if anio in tag:
            score += 1
        if titulo_lower and any(w in titulo_lower for w in tag_key.split() if len(w) > 3):
            score += 2

        scored.append((tag, score))

    scored.sort(key=lambda x: x[1], reverse=True)

    final = []
    chars_usados = 0
    for tag, _ in scored:
        necesita = len(tag) + (1 if final else 0)
        if chars_usados + necesita > YOUTUBE_MAX_TAG_CHARS:
            break
        final.append(tag)
        chars_usados += necesita

    return final

SYSTEM_PROMPT_SEO = """Eres un consultor SEO experto en YouTube. Te paso el
titulo ganador, el nicho del canal y el guion completo de un video.

Genera metadata optimizada para YouTube:
- descripcion: 2-3 parrafos optimizados para SEO, con las palabras
  clave del nicho usadas de forma natural (sin relleno forzado), y
  terminando con una llamada a la accion para suscribirse.
- tags: lista de 10 a 15 tags relevantes (palabras o frases cortas).
- categoria: una categoria de YouTube apropiada (ej. "Education",
  "Howto & Style", "Entertainment", "People & Blogs", "Science & Technology").
- titulos_capitulo: lista de titulos cortos (3 a 6 palabras) para
  cada escena del guion, en el MISMO ORDEN que las escenas, resumiendo
  de que trata cada una (se usaran como capitulos del video).

SIEMPRE respondes en JSON valido:
{
  "descripcion": "...",
  "tags": ["...", "..."],
  "categoria": "...",
  "titulos_capitulo": ["...", "..."]
}
Debes devolver EXACTAMENTE un titulo_capitulo por cada escena que te paso, en el mismo orden."""


def _formatear_tiempo_capitulo(segundos: float) -> str:
    segundos = int(segundos)
    horas, resto = divmod(segundos, 3600)
    minutos, segs = divmod(resto, 60)
    if horas:
        return f"{horas:d}:{minutos:02d}:{segs:02d}"
    return f"{minutos:d}:{segs:02d}"


def _construir_capitulos(escenas: list[dict], duraciones: dict[int, float], titulos_capitulo: list[str]) -> list[dict]:
    capitulos = []
    tiempo_acumulado = 0.0
    ultimo_inicio_aceptado = None

    for escena, titulo in zip(escenas, titulos_capitulo):
        inicio = tiempo_acumulado
        if ultimo_inicio_aceptado is None or inicio - ultimo_inicio_aceptado >= SEPARACION_MINIMA_CAPITULOS_SEG:
            capitulos.append({"tiempo": _formatear_tiempo_capitulo(inicio), "titulo": titulo})
            ultimo_inicio_aceptado = inicio
        tiempo_acumulado += duraciones[escena["numero"]]

    return capitulos


def logica(request: AgenteRequest) -> dict:
    estado = state.leer(request.proyecto_id)

    if not estado.video_final_path:
        raise ValueError("No hay video final: corre primero el Agente 5.1 (Editor)")

    escenas = [e.model_dump() for e in estado.guion.escenas]
    if not escenas:
        raise ValueError("No hay escenas en el guion")

    from moviepy import VideoFileClip  # import diferido, solo para leer la duracion real

    duracion_total = VideoFileClip(estado.video_final_path).duration
    duraciones = calcular_duraciones_por_palabras(escenas, duracion_total)

    # Performance feedback: que fuentes de trafico funcionan
    seo_feedback = ""
    canal_id = estado.estrategia.canal_id or estado.canal_id
    if canal_id:
        try:
            canal = channels.leer(canal_id)
            promedios = canal.promedios_canal
            if promedios.total_videos_analizados >= 3:
                seo_feedback += f"""

Datos de performance del canal para optimizar SEO:
- CTR promedio: {promedios.ctr_promedio or '?'}%
- Videos analizados: {promedios.total_videos_analizados}"""

            # Tags de videos exitosos como referencia
            exitosos = canal.patrones_exitosos[-3:]
            if exitosos:
                titulos_ref = [f"- \"{p.get('titulo', '?')}\" ({p.get('vistas', 0):,} vistas)" for p in exitosos]
                seo_feedback += f"""

Videos con mejor rendimiento (usa como referencia de tono y keywords):
{chr(10).join(titulos_ref)}"""
        except FileNotFoundError:
            pass

    user_prompt = f"""Titulo: {estado.estrategia.titulo_ganador or ""}
Nicho: {estado.estrategia.nicho}
Numero de escenas: {len(escenas)}

Guion completo:
{estado.guion.texto_completo or ""}{seo_feedback}"""

    user_prompt = inyectar_knowledge(user_prompt, "depto_5_cierre")
    resultado = generar_json(SYSTEM_PROMPT_SEO, user_prompt, temperatura=0.6)

    titulos_capitulo = resultado.get("titulos_capitulo") or []
    if len(titulos_capitulo) != len(escenas):
        # Defensivo: si Groq no devolvio la cantidad exacta, rellenamos
        # con el tipo de escena como titulo generico y recortamos al
        # tamano correcto -- nunca dejamos que esto rompa el agente.
        relleno = [e["tipo"].capitalize() for e in escenas]
        titulos_capitulo = (titulos_capitulo + relleno)[: len(escenas)]

    capitulos = _construir_capitulos(escenas, duraciones, titulos_capitulo)

    tags_raw = resultado.get("tags", [])
    tags = _priorizar_tags(
        tags_raw,
        nicho=estado.estrategia.nicho or "",
        titulo=estado.estrategia.titulo_ganador or "",
        keywords=estado.estrategia.patrones_virales or [],
    )

    metadata = {
        "descripcion": resultado.get("descripcion", ""),
        "tags": tags,
        "categoria": resultado.get("categoria"),
        "capitulos": capitulos,
    }

    state.actualizar(request.proyecto_id, metadata=metadata)
    return {"metadata": metadata}


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
