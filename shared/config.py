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
SUNO_API_KEY = os.getenv("SUNO_API_KEY", "")
SUNO_API_BASE_URL = os.getenv("SUNO_API_BASE_URL", "")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
RESOLUCION_VIDEO = os.getenv("RESOLUCION_VIDEO", "1920x1080")
FPS_VIDEO = int(os.getenv("FPS_VIDEO", "30"))
SUBTITULOS_FONT_PATH = os.getenv("SUBTITULOS_FONT_PATH", "")
KAGGLE_USERNAME = os.getenv("KAGGLE_USERNAME", "")
KAGGLE_KEY = os.getenv("KAGGLE_KEY", "")
KAGGLE_DATASET_SLUG = os.getenv("KAGGLE_DATASET_SLUG", f"{KAGGLE_USERNAME}/ytcreator-prompts")
KAGGLE_KERNEL_SLUG = os.getenv("KAGGLE_KERNEL_SLUG", f"{KAGGLE_USERNAME}/youtube-ai-studio-v7-hibrido")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
STORAGE_DIR = os.getenv("STORAGE_DIR", ".")

# -- registro de puertos: agente_id -> puerto -------------------------------
REGISTRO_AGENTES: dict[str, int] = {
    # Depto 1 - Estrategia
    "sub_orq_estrategia": 8110,
    "1.1_investigador": 8101,
    "1.2_copywriter": 8102,
    "1.3_director_arte": 8103,
    # Depto 2 - Guion
    "2.1_guionista": 8201,
    "2.2_evaluador": 8202,
    # Depto 3 - Visual
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
    # Orquestador central
    "orquestador_central": 8000,
}


def url_agente(agente_id: str) -> str:
    """Devuelve la URL base de un agente a partir de su id en el registro."""
    puerto = REGISTRO_AGENTES[agente_id]
    return f"http://localhost:{puerto}"
