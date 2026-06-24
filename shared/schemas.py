"""
Contrato de comunicacion entre agentes - YTCreator Studio
============================================================

Este archivo es la UNICA fuente de verdad sobre la forma del estado
de un proyecto de video. Todos los agentes leen y escriben usando
estos modelos. Si necesitas agregar un campo nuevo, se agrega AQUI
primero y luego se usa en el agente correspondiente.

Estructura general de un proyecto:

    EstadoProyecto
    |-- estrategia   (Depto 1: nicho, titulo, miniatura)
    |-- guion         (Depto 2: hook/cuerpo/cta, score, aprobado)
    |-- visual        (Depto 3: prompts, imagenes, clips)
    |-- audio         (Depto 4: voz, musica, subtitulos)
    |-- metadata       (Depto 5: descripcion, tags, seo)
    |-- historial_agentes (auditoria: quien corrio, cuando, que paso)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class EstadoFase(str, Enum):
    PENDIENTE = "pendiente"
    EN_PROCESO = "en_proceso"
    COMPLETADO = "completado"
    ERROR = "error"
    ESPERANDO_APROBACION = "esperando_aprobacion"


class ResultadoAgente(BaseModel):
    """Una entrada en el historial: que agente corrio, cuando, y que paso."""
    agente_id: str
    estado: EstadoFase
    intentos: int = 1
    inicio: Optional[datetime] = None
    fin: Optional[datetime] = None
    error: Optional[str] = None
    duracion_seg: Optional[float] = None


# ---------------------------------------------------------------------------
# Depto 1 - Estrategia (Agentes 1.1 Investigador, 1.2 Copywriter, 1.3 Dir. Arte)
# ---------------------------------------------------------------------------

class BriefEstrategia(BaseModel):
    nicho: str = ""
    canal_tono: Optional[str] = None  # ej. "educativo serio", "entretenimiento rapido"
    patrones_virales: list[str] = Field(default_factory=list)
    titulos_candidatos: list[str] = Field(default_factory=list)
    titulo_ganador: Optional[str] = None
    titulo_score: Optional[float] = None
    titulo_subcampeon: Optional[str] = None  # 2do lugar - util como backup o variante A/B
    mood: Optional[str] = None  # usado por Depto 4 (audio) para elegir musica/tono de voz
    miniatura_prompt: Optional[str] = None
    miniatura_composicion: Optional[dict] = None
    miniatura_path: Optional[str] = None
    # Channel Intelligence (Depto 0) - inyectado por sub_orq_inteligencia
    canal_id: Optional[str] = None
    contexto_canal: Optional[dict] = None
    competidores_contexto: Optional[list[dict]] = None
    tendencias_nicho: Optional[list[str]] = None
    brechas_contenido: Optional[list[str]] = None


# ---------------------------------------------------------------------------
# Depto 2 - Guion (Agentes 2.1 Guionista, 2.2 Evaluador)
# ---------------------------------------------------------------------------

class Escena(BaseModel):
    numero: int
    texto: str
    tipo: Literal["hook", "cuerpo", "cta"]
    prompt_visual: Optional[str] = None
    usa_video_ia: bool = False
    archivo_generado: Optional[str] = None


class Guion(BaseModel):
    texto_completo: Optional[str] = None
    escenas: list[Escena] = Field(default_factory=list)
    score: Optional[float] = None
    intentos_reescritura: int = 0
    aprobado: bool = False
    feedback_evaluador: Optional[str] = None


# ---------------------------------------------------------------------------
# Depto 3 - Visual (Agentes 3.1 Prompt Maker, 3.2 Generador Visual)
# ---------------------------------------------------------------------------

class AssetsVisuales(BaseModel):
    prompts_generados: bool = False
    generacion_completada: bool = False
    imagenes: list[str] = Field(default_factory=list)
    clips_video: list[str] = Field(default_factory=list)
    candados_aplicados: Optional[dict] = None  # snapshot de los 5 Candados usados


# ---------------------------------------------------------------------------
# Depto 4 - Audio (Agentes 4.1 Locucion, 4.2 Musica, 4.3 Subtitulos)
# ---------------------------------------------------------------------------

class AssetsAudio(BaseModel):
    voz_path: Optional[str] = None
    voz_config: Optional[dict] = None  # rate, pitch, voice_id (Edge TTS)
    musica_path: Optional[str] = None
    musica_fuente: Optional[Literal["musicgen", "pixabay"]] = None
    musica_volumen_db: Optional[float] = None
    musicgen_error: Optional[str] = None
    subtitulos_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Depto 5 - Cierre (Agentes 5.1 Editor Tecnico, 5.2 Consultor SEO)
# ---------------------------------------------------------------------------

class Metadata(BaseModel):
    descripcion: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    categoria: Optional[str] = None
    capitulos: list[dict] = Field(default_factory=list)


class Compliance(BaseModel):
    nivel_riesgo: Optional[Literal["bajo", "medio", "alto", "critico"]] = None
    aprobado: Optional[bool] = None
    warnings: list[dict] = Field(default_factory=list)
    resumen: Optional[str] = None


# ---------------------------------------------------------------------------
# Estado completo del proyecto
# ---------------------------------------------------------------------------

class EstadoProyecto(BaseModel):
    proyecto_id: str
    canal: str
    canal_id: Optional[str] = None
    creado_en: datetime
    actualizado_en: datetime
    fase_actual: Literal[
        "estrategia", "guion", "visual", "audio", "cierre", "completado", "publicado", "error"
    ] = "estrategia"

    estrategia: BriefEstrategia = Field(default_factory=BriefEstrategia)
    guion: Guion = Field(default_factory=Guion)
    visual: AssetsVisuales = Field(default_factory=AssetsVisuales)
    audio: AssetsAudio = Field(default_factory=AssetsAudio)
    metadata: Metadata = Field(default_factory=Metadata)
    compliance: Compliance = Field(default_factory=Compliance)

    video_final_path: Optional[str] = None
    publicado: bool = False
    youtube_video_id: Optional[str] = None
    publicado_en: Optional[datetime] = None

    performance: Optional[PerformanceTracking] = None

    agente_actual: Optional[str] = None
    historial_agentes: list[ResultadoAgente] = Field(default_factory=list)
    errores: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Depto 0 - Inteligencia de Canal (Agentes 0.1-0.4)
# ---------------------------------------------------------------------------

class VideoRendimiento(BaseModel):
    video_id: str
    titulo: str
    publicado_en: Optional[datetime] = None
    vistas: int = 0
    likes: int = 0
    comentarios: int = 0
    duracion_seg: Optional[int] = None
    miniatura_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    categoria_id: Optional[str] = None


class CompetidorInfo(BaseModel):
    channel_id: str
    nombre: str
    suscriptores: Optional[int] = None
    video_count: Optional[int] = None
    ultimo_escaneo: Optional[datetime] = None
    videos_recientes: list[VideoRendimiento] = Field(default_factory=list)
    top_videos: list[VideoRendimiento] = Field(default_factory=list)


class PerfilCanal(BaseModel):
    nicho_principal: str = ""
    sub_nichos: list[str] = Field(default_factory=list)
    keywords_clave: list[str] = Field(default_factory=list)
    tono: Optional[str] = None
    estilo_visual: Optional[str] = None
    audiencia_objetivo: Optional[str] = None
    formatos_exitosos: list[str] = Field(default_factory=list)
    frecuencia_publicacion: Optional[str] = None
    mejores_horarios: list[str] = Field(default_factory=list)
    patrones_titulo_exitosos: list[str] = Field(default_factory=list)
    duracion_promedio_seg: Optional[int] = None


class EstadoCanal(BaseModel):
    canal_id: str
    nombre: str
    descripcion: Optional[str] = None
    url: Optional[str] = None
    suscriptores: Optional[int] = None
    video_count: Optional[int] = None
    vistas_totales: Optional[int] = None
    creado_youtube: Optional[datetime] = None
    miniatura_url: Optional[str] = None
    banner_url: Optional[str] = None
    uploads_playlist_id: Optional[str] = None

    oauth_conectado: bool = False

    perfil: PerfilCanal = Field(default_factory=PerfilCanal)

    videos_recientes: list[VideoRendimiento] = Field(default_factory=list)
    top_videos: list[VideoRendimiento] = Field(default_factory=list)

    competidores: list[CompetidorInfo] = Field(default_factory=list)

    escaneado_en: Optional[datetime] = None
    perfil_analizado_en: Optional[datetime] = None
    competidores_actualizados_en: Optional[datetime] = None

    tendencias_nicho: list[str] = Field(default_factory=list)
    brechas_contenido: list[str] = Field(default_factory=list)
    ideas_sugeridas: list[dict] = Field(default_factory=list)

    promedios_canal: PromediosCanal = Field(default_factory=PromediosCanal)
    performance_historial: list[dict] = Field(default_factory=list)
    patrones_exitosos: list[dict] = Field(default_factory=list)
    patrones_a_evitar: list[dict] = Field(default_factory=list)


class QuotaTracker(BaseModel):
    fecha: str
    unidades_usadas: int = 0
    detalle: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Depto 0 - Performance Tracking (Agente 0.5 Tracker Performance)
# ---------------------------------------------------------------------------

class CheckpointTipo(str, Enum):
    T_24H = "t_24h"
    T_48H = "t_48h"
    T_72H = "t_72h"
    T_7D = "t_7d"
    T_30D = "t_30d"


class GradePerformance(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class MetricasVideo(BaseModel):
    vistas: int = 0
    likes: int = 0
    comentarios: int = 0
    ctr: Optional[float] = None
    retencion_promedio: Optional[float] = None
    tiempo_visto_min: Optional[float] = None
    duracion_vista_promedio_seg: Optional[float] = None
    engagement_rate: Optional[float] = None


class TrafficSources(BaseModel):
    search: float = 0.0
    suggested: float = 0.0
    external: float = 0.0
    browse: float = 0.0
    otros: float = 0.0


class DemografiaAudiencia(BaseModel):
    top_pais: Optional[str] = None
    top_edad: Optional[str] = None
    top_genero: Optional[str] = None


class AccionCorrectiva(BaseModel):
    tipo: Literal[
        "cambiar_thumbnail", "cambiar_titulo", "mejorar_seo",
        "ajustar_estrategia", "replicar_patron", "informativa",
    ]
    prioridad: Literal["alta", "media", "baja"]
    descripcion: str
    agente_destino: Optional[str] = None
    datos: dict = Field(default_factory=dict)


class PerformanceCheckpoint(BaseModel):
    tipo: CheckpointTipo
    timestamp: datetime
    metricas: MetricasVideo = Field(default_factory=MetricasVideo)
    traffic_sources: Optional[TrafficSources] = None
    demografia: Optional[DemografiaAudiencia] = None
    grade: Optional[GradePerformance] = None
    score: Optional[float] = None
    vs_promedio_canal: Optional[dict] = None
    insights: list[str] = Field(default_factory=list)
    acciones: list[AccionCorrectiva] = Field(default_factory=list)


class PerformanceTracking(BaseModel):
    video_id: str
    proyecto_id: str
    canal_id: str
    titulo: str
    publicado_en: datetime
    checkpoints: list[PerformanceCheckpoint] = Field(default_factory=list)
    grade_actual: Optional[GradePerformance] = None
    patrones_identificados: list[str] = Field(default_factory=list)


class PromediosCanal(BaseModel):
    total_videos_analizados: int = 0
    vistas_promedio: float = 0.0
    likes_promedio: float = 0.0
    comentarios_promedio: float = 0.0
    ctr_promedio: Optional[float] = None
    retencion_promedio: Optional[float] = None
    engagement_rate_promedio: Optional[float] = None
    actualizado_en: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Contrato de request/response entre orquestador y cada agente (HTTP)
# ---------------------------------------------------------------------------

class AgenteRequest(BaseModel):
    proyecto_id: str
    parametros: dict = Field(default_factory=dict)


class AgenteResponse(BaseModel):
    agente_id: str
    estado: Literal["completado", "error"]
    output: Optional[dict] = None
    error: Optional[str] = None
    duracion_seg: Optional[float] = None
