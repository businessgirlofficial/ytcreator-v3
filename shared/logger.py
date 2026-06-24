"""
Logging centralizado - YTCreator Studio
==========================================

Un solo lugar para configurar el formato, nivel y destino de los logs
de todos los microservicios. Cada agente llama a get_logger("agente_id")
y recibe un logger con formato consistente.

Destinos:
  - stdout (para Docker, HF Spaces, run_dev.py)
  - archivo rotativo en logs/ (para persistencia local)
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import STORAGE_DIR

LOGS_DIR = Path(STORAGE_DIR) / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_LEVEL = logging.INFO

MAX_BYTES = 5 * 1024 * 1024  # 5 MB por archivo
BACKUP_COUNT = 3

_configurado = set()


def get_logger(nombre: str) -> logging.Logger:
    if nombre in _configurado:
        return logging.getLogger(nombre)

    logger = logging.getLogger(nombre)
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    archivo = RotatingFileHandler(
        str(LOGS_DIR / "ytcreator.log"),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    archivo.setFormatter(formatter)
    logger.addHandler(archivo)

    _configurado.add(nombre)
    return logger
