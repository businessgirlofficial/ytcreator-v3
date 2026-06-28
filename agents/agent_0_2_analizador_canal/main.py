"""
Agente 0.2 - Analizador de Canal
Depto 0 (Inteligencia de Canal)

Toma los datos crudos del escaneo (Agent 0.1) y los analiza:
  1. Stats deterministicos en codigo (promedios, frecuencia, top categorias)
  2. Analisis IA con Groq (nicho, tono, audiencia, patrones de exito)

Resultado: un PerfilCanal completo que informa todas las decisiones
de contenido del pipeline de creacion de videos.
"""

import sys
from collections import Counter
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

AGENTE_ID = "0.2_analizador_canal"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Analiza datos del canal con IA para extraer perfil estrategico")
channels = ChannelManager()

SYSTEM_PROMPT = """Eres un analista experto de canales de YouTube. Recibes datos reales de
un canal (estadisticas, titulos de videos, descripcion) y extraes un perfil estrategico.

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "nicho_principal": "el nicho central del canal en 2-4 palabras",
  "subnicho_principal": "el subnicho MAS ESPECIFICO del canal (ej: NO 'espiritualidad' sino 'meditaciones guiadas para dormir', NO 'fitness' sino 'rutinas HIIT para mujeres en casa'). Debe describir el angulo concreto que diferencia este canal y apunta a un grupo especifico de personas",
  "sub_nichos": ["subnicho 1", "subnicho 2"],
  "keywords_clave": ["keyword 1", "keyword 2", "keyword 3", "keyword 4", "keyword 5"],
  "tono": "descripcion del tono del canal (ej: educativo serio, entretenimiento rapido, conversacional cercano)",
  "estilo_visual": "descripcion del estilo visual predominante en miniaturas/contenido",
  "audiencia_objetivo": "descripcion de la audiencia objetivo en 1-2 frases",
  "formatos_exitosos": ["formato 1 que funciona (ej: listicle, storytime, tutorial)", "formato 2"],
  "patrones_titulo_exitosos": ["patron 1 concreto (ej: 'numero + palabra de shock')", "patron 2"],
  "frecuencia_recomendada": "frecuencia de publicacion recomendada basada en los datos"
}

IMPORTANTE sobre el subnicho_principal:
- El nicho es la categoria amplia (ej: espiritualidad, fitness, finanzas).
- El subnicho_principal es el ENFOQUE ESPECIFICO que hace unico al canal.
- Debe ser lo suficientemente concreto para buscar competidores directos.
- Piensa: ¿a que grupo MUY especifico de personas le habla este canal?

Basa tu analisis SOLO en los datos proporcionados. Se concreto y accionable."""


def _computar_stats(estado) -> dict:
    videos = estado.videos_recientes
    if not videos:
        return {"total_videos": 0}

    vistas = [v.vistas for v in videos]
    likes = [v.likes for v in videos]
    comentarios = [v.comentarios for v in videos]
    duraciones = [v.duracion_seg for v in videos if v.duracion_seg]

    categorias = Counter(v.categoria_id for v in videos if v.categoria_id)

    titulos = [v.titulo for v in videos]
    largos_titulo = [len(t) for t in titulos]

    fechas = sorted(
        [v.publicado_en for v in videos if v.publicado_en],
        reverse=True,
    )
    freq_dias = None
    if len(fechas) >= 2:
        deltas = [(fechas[i] - fechas[i + 1]).days for i in range(min(len(fechas) - 1, 20))]
        freq_dias = sum(deltas) / len(deltas) if deltas else None

    return {
        "total_videos": len(videos),
        "vistas_promedio": round(sum(vistas) / len(vistas)),
        "vistas_mediana": sorted(vistas)[len(vistas) // 2],
        "likes_promedio": round(sum(likes) / len(likes)),
        "comentarios_promedio": round(sum(comentarios) / len(comentarios)),
        "duracion_promedio_seg": round(sum(duraciones) / len(duraciones)) if duraciones else None,
        "largo_titulo_promedio": round(sum(largos_titulo) / len(largos_titulo)),
        "top_categorias": dict(categorias.most_common(3)),
        "frecuencia_dias_entre_videos": round(freq_dias, 1) if freq_dias else None,
    }


def logica(request: AgenteRequest) -> dict:
    canal_id = request.parametros.get("canal_id", "")
    if not canal_id:
        raise ValueError("Falta el parametro 'canal_id'")

    estado = channels.leer(canal_id)
    stats = _computar_stats(estado)

    top_titulos = [v.titulo for v in estado.top_videos[:10]]
    titulos_recientes = [v.titulo for v in estado.videos_recientes[:20]]

    user_prompt = f"""Canal: {estado.nombre}
Descripcion del canal: {estado.descripcion or '(sin descripcion)'}
Suscriptores: {estado.suscriptores or 'N/A'}

Estadisticas calculadas:
- Videos analizados: {stats['total_videos']}
- Vistas promedio: {stats.get('vistas_promedio', 'N/A')}
- Vistas mediana: {stats.get('vistas_mediana', 'N/A')}
- Likes promedio: {stats.get('likes_promedio', 'N/A')}
- Comentarios promedio: {stats.get('comentarios_promedio', 'N/A')}
- Duracion promedio: {stats.get('duracion_promedio_seg', 'N/A')} segundos
- Largo promedio de titulo: {stats.get('largo_titulo_promedio', 'N/A')} caracteres
- Frecuencia: cada {stats.get('frecuencia_dias_entre_videos', 'N/A')} dias

Top 10 videos por vistas:
{chr(10).join(f'- {t}' for t in top_titulos) if top_titulos else '(sin datos)'}

Ultimos 20 titulos publicados:
{chr(10).join(f'- {t}' for t in titulos_recientes) if titulos_recientes else '(sin datos)'}

Analiza este canal y genera su perfil estrategico."""

    user_prompt = inyectar_knowledge(user_prompt, "depto_0_inteligencia")
    resultado = generar_json(SYSTEM_PROMPT, user_prompt)

    freq_texto = None
    freq_dias = stats.get("frecuencia_dias_entre_videos")
    if freq_dias:
        if freq_dias <= 1:
            freq_texto = "diario"
        elif freq_dias <= 3.5:
            freq_texto = f"{round(7 / freq_dias)} videos/semana"
        elif freq_dias <= 7:
            freq_texto = "1 video/semana"
        else:
            freq_texto = f"1 video cada {round(freq_dias)} dias"

    perfil_data = {
        "nicho_principal": resultado.get("nicho_principal", ""),
        "subnicho_principal": resultado.get("subnicho_principal", ""),
        "sub_nichos": resultado.get("sub_nichos", []),
        "keywords_clave": resultado.get("keywords_clave", []),
        "tono": resultado.get("tono"),
        "estilo_visual": resultado.get("estilo_visual"),
        "audiencia_objetivo": resultado.get("audiencia_objetivo"),
        "formatos_exitosos": resultado.get("formatos_exitosos", []),
        "frecuencia_publicacion": freq_texto or resultado.get("frecuencia_recomendada"),
        "patrones_titulo_exitosos": resultado.get("patrones_titulo_exitosos", []),
        "duracion_promedio_seg": stats.get("duracion_promedio_seg"),
    }

    channels.actualizar(
        canal_id,
        perfil=perfil_data,
        perfil_analizado_en=datetime.utcnow().isoformat(),
    )

    return {
        "canal_id": canal_id,
        "perfil": perfil_data,
        "stats": stats,
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
