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
    musica_fuente: Optional[Literal["pixabay", "suno"]] = None
    musica_volumen_db: Optional[float] = None
    subtitulos_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Depto 5 - Cierre (Agentes 5.1 Editor Tecnico, 5.2 Consultor SEO)
# ---------------------------------------------------------------------------

class Metadata(BaseModel):
    descripcion: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    categoria: Optional[str] = None
    capitulos: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Estado completo del proyecto
# ---------------------------------------------------------------------------

class EstadoProyecto(BaseModel):
    proyecto_id: str
    canal: str
    creado_en: datetime
    actualizado_en: datetime
    fase_actual: Literal[
        "estrategia", "guion", "visual", "audio", "cierre", "publicado", "error"
    ] = "estrategia"

    estrategia: BriefEstrategia = Field(default_factory=BriefEstrategia)
    guion: Guion = Field(default_factory=Guion)
    visual: AssetsVisuales = Field(default_factory=AssetsVisuales)
    audio: AssetsAudio = Field(default_factory=AssetsAudio)
    metadata: Metadata = Field(default_factory=Metadata)

    video_final_path: Optional[str] = None
    publicado: bool = False
    youtube_video_id: Optional[str] = None

    historial_agentes: list[ResultadoAgente] = Field(default_factory=list)
    errores: list[str] = Field(default_factory=list)


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
