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
from shared.config import REGISTRO_AGENTES
from shared.groq_client import generar_json
from shared.schemas import AgenteRequest, AgenteResponse
from shared.state_manager import StateManager
from shared.video_utils import calcular_duraciones_por_palabras

AGENTE_ID = "5.2_seo"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Genera descripcion, tags, categoria y capitulos con Groq")
state = StateManager()

SEPARACION_MINIMA_CAPITULOS_SEG = 10  # requisito real de YouTube

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

    user_prompt = f"""Titulo: {estado.estrategia.titulo_ganador or ""}
Nicho: {estado.estrategia.nicho}
Numero de escenas: {len(escenas)}

Guion completo:
{estado.guion.texto_completo or ""}"""

    resultado = generar_json(SYSTEM_PROMPT_SEO, user_prompt, temperatura=0.6)

    titulos_capitulo = resultado.get("titulos_capitulo") or []
    if len(titulos_capitulo) != len(escenas):
        # Defensivo: si Groq no devolvio la cantidad exacta, rellenamos
        # con el tipo de escena como titulo generico y recortamos al
        # tamano correcto -- nunca dejamos que esto rompa el agente.
        relleno = [e["tipo"].capitalize() for e in escenas]
        titulos_capitulo = (titulos_capitulo + relleno)[: len(escenas)]

    capitulos = _construir_capitulos(escenas, duraciones, titulos_capitulo)

    metadata = {
        "descripcion": resultado.get("descripcion", ""),
        "tags": resultado.get("tags", []),
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
