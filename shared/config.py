"""
Configuracion compartida - YTCreator Studio
=============================================

Carga las variables de entorno (.env) y mantiene el REGISTRO de
agentes con su puerto. Este registro es el unico lugar donde se
define donde vive cada microservicio - asi el orquestador (y los
sub-orquestadores) saben a que URL llamar sin tener nada hardcodeado
repetido en cada archivo.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# -- claves de API (copialas desde tu .env actual de YTCreator Studio v3) --
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
RESOLUCION_VIDEO = os.getenv("RESOLUCION_VIDEO", "1920x1080")
FPS_VIDEO = int(os.getenv("FPS_VIDEO", "30"))
SUBTITULOS_FONT_PATH = os.getenv("SUBTITULOS_FONT_PATH", "")
SUBTITULOS_PALABRAS_POR_BLOQUE = int(os.getenv("SUBTITULOS_PALABRAS_POR_BLOQUE", "3"))
KAGGLE_USERNAME = os.getenv("KAGGLE_USERNAME", "")
KAGGLE_KEY = os.getenv("KAGGLE_KEY", "")
KAGGLE_DATASET_SLUG = os.getenv("KAGGLE_DATASET_SLUG", f"{KAGGLE_USERNAME}/ytcreator-prompts")
KAGGLE_KERNEL_SLUG = os.getenv("KAGGLE_KERNEL_SLUG", f"{KAGGLE_USERNAME}/youtube-ai-studio-v7-hibrido")
MODAL_TOKEN_ID = os.getenv("MODAL_TOKEN_ID", "")
MODAL_TOKEN_SECRET = os.getenv("MODAL_TOKEN_SECRET", "")
BEAM_API_KEY = os.getenv("BEAM_API_KEY", "")
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YTCREATOR_API_KEY = os.getenv("YTCREATOR_API_KEY", "")
STORAGE_DIR = os.getenv("STORAGE_DIR", ".")
ARCHIVE_DIR = os.getenv("ARCHIVE_DIR", r"D:\ytcreator_archive")
BUFFER_MAX_VIDEOS = int(os.getenv("BUFFER_MAX_VIDEOS", "3"))

# -- Telegram Notifications --
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_NOTIFICATIONS = os.getenv("TELEGRAM_NOTIFICATIONS", "true").lower() == "true"
TELEGRAM_PC_LABEL = os.getenv("TELEGRAM_PC_LABEL", "")

# -- rate limits (requests por minuto, ajustar segun tu tier) ----
GROQ_RATE_LIMIT = float(os.getenv("GROQ_RATE_LIMIT", "30"))
HF_RATE_LIMIT = float(os.getenv("HF_RATE_LIMIT", "10"))
PIXABAY_RATE_LIMIT = float(os.getenv("PIXABAY_RATE_LIMIT", "0.83"))
CLAUDE_RATE_LIMIT = float(os.getenv("CLAUDE_RATE_LIMIT", "10"))
RATE_LIMIT_SAFETY_FACTOR = float(os.getenv("RATE_LIMIT_SAFETY_FACTOR", "0.8"))

# -- Claude Code SDK (usa suscripcion Pro, no necesita API key) ----
CLAUDE_MAX_TURNS = int(os.getenv("CLAUDE_MAX_TURNS", "1"))
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# -- limites de tamaño de assets descargados (bytes) ----
MAX_IMAGEN_BYTES = int(os.getenv("MAX_IMAGEN_BYTES", str(50 * 1024 * 1024)))    # 50 MB
MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", str(50 * 1024 * 1024)))      # 50 MB
MAX_VIDEO_BYTES = int(os.getenv("MAX_VIDEO_BYTES", str(500 * 1024 * 1024)))     # 500 MB

# -- registro de puertos: agente_id -> puerto -------------------------------
REGISTRO_AGENTES: dict[str, int] = {
    # Depto 0 - Inteligencia de Canal
    "sub_orq_inteligencia": 8010,
    "0.1_escaner_canal": 8001,
    "0.2_analizador_canal": 8002,
    "0.3_monitor_mercado": 8003,
    "0.4_asesor_estrategico": 8004,
    "0.5_tracker_performance": 8005,
    # Depto 1 - Estrategia
    "sub_orq_estrategia": 8110,
    "1.1_investigador": 8101,
    "1.2_copywriter": 8102,
    "1.3_director_arte": 8103,
    "1.4_generador_miniatura": 8104,
    # Depto 2 - Guion (evaluacion absorbida en sub_orq_guion)
    "sub_orq_guion": 8210,
    "2.1_guionista": 8201,
    # Depto 3 - Visual
    "sub_orq_visual": 8310,
    "3.1_prompt_maker": 8301,
    "3.2_generador_visual": 8302,
    # Depto 4 - Audio
    "sub_orq_audio": 8410,
    "4.1_locucion": 8401,
    "4.2_musica": 8402,
    "4.3_subtitulos": 8403,
    # Depto 5 - Cierre
    "sub_orq_cierre": 8510,
    "5.1_editor": 8501,
    "5.2_seo": 8502,
    "5.3_compliance": 8503,
    "5.4_policy_monitor": 8504,
    "5.5_publicador": 8505,
    # Orquestador central
    "orquestador_central": 8000,
}


def url_agente(agente_id: str) -> str:
    """Devuelve la URL base de un agente a partir de su id en el registro."""
    puerto = REGISTRO_AGENTES[agente_id]
    return f"http://localhost:{puerto}"
