"""
Scheduler - Registro de tareas programadas de YTCreator Studio
================================================================

Mantiene un archivo JSON con la configuracion de las tareas
programadas del sistema (horarios, estado habilitado/deshabilitado,
ultima y proxima ejecucion). NO ejecuta tareas por si solo — la
ejecucion real la maneja n8n u otro orquestador externo.

Este modulo hace visible el schedule desde la UI: que tareas hay,
cuando se ejecutaron, cuando se ejecutaran, y si estan activas.

Almacena la config en scheduler/schedule_config.json con FileLock
para seguridad en escritura.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from filelock import FileLock

from .config import STORAGE_DIR

SCHEDULE_DIR = Path(STORAGE_DIR) / "scheduler"
SCHEDULE_FILE = SCHEDULE_DIR / "schedule_config.json"
LOCK_FILE = SCHEDULE_DIR / "schedule_config.lock"
PAUSE_FILE = SCHEDULE_DIR / "pause_state.json"
PAUSE_LOCK = SCHEDULE_DIR / "pause_state.lock"

DEFAULT_TASKS = [
    {
        "task_id": "video_diario",
        "nombre": "Generar video diario",
        "descripcion": "Pipeline completo: estrategia, guion, visual, audio, cierre",
        "cron": "0 8 * * *",
        "hora_legible": "08:00",
        "frecuencia": "Diario",
        "habilitado": True,
        "orquestador": "n8n",
        "endpoint": "/pipeline/webhook",
        "ultima_ejecucion": None,
        "ultima_duracion_seg": None,
        "ultimo_estado": None,
    },
    {
        "task_id": "performance_checkpoints",
        "nombre": "Evaluar performance",
        "descripcion": "Checkpoints de videos publicados (1h, 24h, 48h, 7d)",
        "cron": "0 */6 * * *",
        "hora_legible": "Cada 6h",
        "frecuencia": "Cada 6 horas",
        "habilitado": True,
        "orquestador": "n8n",
        "endpoint": "/performance/evaluar_pendientes",
        "ultima_ejecucion": None,
        "ultima_duracion_seg": None,
        "ultimo_estado": None,
    },
    {
        "task_id": "health_check",
        "nombre": "Health check servicios",
        "descripcion": "Verifica que todos los microservicios esten activos",
        "cron": "*/15 * * * *",
        "hora_legible": "Cada 15 min",
        "frecuencia": "Cada 15 minutos",
        "habilitado": True,
        "orquestador": "n8n",
        "endpoint": "/scheduling/health_servicios",
        "ultima_ejecucion": None,
        "ultima_duracion_seg": None,
        "ultimo_estado": None,
    },
    {
        "task_id": "cronograma_diario",
        "nombre": "Ejecutar cronograma",
        "descripcion": "Revisa vigencia y produce el video del dia segun el cronograma y el modo (manual/semi/auto)",
        "cron": "0 8 * * *",
        "hora_legible": "08:00",
        "frecuencia": "Diario",
        "habilitado": True,
        "orquestador": "n8n",
        "endpoint": "/cronograma/ejecutar_diario",
        "ultima_ejecucion": None,
        "ultima_duracion_seg": None,
        "ultimo_estado": None,
    },
    {
        "task_id": "purgar_eventos",
        "nombre": "Limpiar eventos antiguos",
        "descripcion": "Elimina eventos de automatizacion con mas de 90 dias",
        "cron": "0 3 * * 0",
        "hora_legible": "Dom 03:00",
        "frecuencia": "Semanal (domingos)",
        "habilitado": True,
        "orquestador": "interno",
        "endpoint": "/eventos/purgar",
        "ultima_ejecucion": None,
        "ultima_duracion_seg": None,
        "ultimo_estado": None,
    },
]


def _ensure_dir():
    SCHEDULE_DIR.mkdir(parents=True, exist_ok=True)


def _leer() -> list[dict]:
    _ensure_dir()
    if not SCHEDULE_FILE.exists():
        _escribir(DEFAULT_TASKS)
        return DEFAULT_TASKS
    lock = FileLock(str(LOCK_FILE))
    with lock:
        data = json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
    return data


def _escribir(tasks: list[dict]):
    _ensure_dir()
    lock = FileLock(str(LOCK_FILE))
    with lock:
        SCHEDULE_FILE.write_text(
            json.dumps(tasks, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )


def listar_tareas() -> list[dict]:
    tasks = _leer()
    ahora = datetime.utcnow()
    for t in tasks:
        t["proxima_ejecucion"] = _calcular_proxima(t["cron"], ahora) if t["habilitado"] else None
    return tasks


def obtener_tarea(task_id: str) -> dict | None:
    tasks = _leer()
    for t in tasks:
        if t["task_id"] == task_id:
            ahora = datetime.utcnow()
            t["proxima_ejecucion"] = _calcular_proxima(t["cron"], ahora) if t["habilitado"] else None
            return t
    return None


def toggle_tarea(task_id: str, habilitado: bool) -> dict | None:
    tasks = _leer()
    for t in tasks:
        if t["task_id"] == task_id:
            t["habilitado"] = habilitado
            _escribir(tasks)
            return t
    return None


def registrar_ejecucion(task_id: str, estado: str, duracion_seg: float | None = None):
    tasks = _leer()
    for t in tasks:
        if t["task_id"] == task_id:
            t["ultima_ejecucion"] = datetime.utcnow().isoformat(timespec="seconds")
            t["ultimo_estado"] = estado
            t["ultima_duracion_seg"] = duracion_seg
            _escribir(tasks)
            return t
    return None


def agregar_tarea(task: dict) -> list[dict]:
    tasks = _leer()
    existing_ids = {t["task_id"] for t in tasks}
    if task["task_id"] in existing_ids:
        tasks = [t if t["task_id"] != task["task_id"] else {**t, **task} for t in tasks]
    else:
        tasks.append(task)
    _escribir(tasks)
    return tasks


def eliminar_tarea(task_id: str) -> bool:
    tasks = _leer()
    filtered = [t for t in tasks if t["task_id"] != task_id]
    if len(filtered) == len(tasks):
        return False
    _escribir(filtered)
    return True


def resumen() -> dict:
    tasks = listar_tareas()
    habilitadas = sum(1 for t in tasks if t["habilitado"])
    ahora = datetime.utcnow()

    proxima = None
    proxima_nombre = None
    for t in tasks:
        if t["habilitado"] and t.get("proxima_ejecucion"):
            if proxima is None or t["proxima_ejecucion"] < proxima:
                proxima = t["proxima_ejecucion"]
                proxima_nombre = t["nombre"]

    pausa = obtener_pausa()

    return {
        "total_tareas": len(tasks),
        "habilitadas": habilitadas,
        "deshabilitadas": len(tasks) - habilitadas,
        "proxima_ejecucion": proxima if not pausa["pausado"] else None,
        "proxima_tarea": proxima_nombre if not pausa["pausado"] else None,
        "pausa": pausa,
        "tareas": tasks,
    }


# ── Pausa global de automatización ──────────────────────────────


def _leer_pausa() -> dict:
    _ensure_dir()
    default = {"pausado": False, "pausado_en": None, "pausado_por": None, "razon": None}
    if not PAUSE_FILE.exists():
        return default
    lock = FileLock(str(PAUSE_LOCK))
    with lock:
        try:
            data = json.loads(PAUSE_FILE.read_text(encoding="utf-8"))
            return {**default, **data}
        except (json.JSONDecodeError, TypeError):
            return default


def _escribir_pausa(data: dict):
    _ensure_dir()
    lock = FileLock(str(PAUSE_LOCK))
    with lock:
        PAUSE_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )


def obtener_pausa() -> dict:
    return _leer_pausa()


def esta_pausado() -> bool:
    return _leer_pausa()["pausado"]


def pausar(razon: str | None = None, por: str = "usuario") -> dict:
    data = {
        "pausado": True,
        "pausado_en": datetime.utcnow().isoformat(timespec="seconds"),
        "pausado_por": por,
        "razon": razon,
    }
    _escribir_pausa(data)
    return data


def reanudar() -> dict:
    data = {
        "pausado": False,
        "pausado_en": None,
        "pausado_por": None,
        "razon": None,
    }
    _escribir_pausa(data)
    return data


def _calcular_proxima(cron_expr: str, ahora: datetime) -> str | None:
    """Calcula la proxima ejecucion a partir de una expresion cron simplificada.
    Soporta: minuto hora dia_mes mes dia_semana con */N y valores fijos."""
    try:
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return None

        minuto_p, hora_p, dom_p, mes_p, dow_p = parts

        def _parse_field(field: str, max_val: int, min_val: int = 0) -> list[int]:
            if field == "*":
                return list(range(min_val, max_val + 1))
            if field.startswith("*/"):
                step = int(field[2:])
                return list(range(min_val, max_val + 1, step))
            if "," in field:
                return [int(x) for x in field.split(",")]
            return [int(field)]

        minutos = _parse_field(minuto_p, 59)
        horas = _parse_field(hora_p, 23)
        dows = _parse_field(dow_p, 6) if dow_p != "*" else None

        candidato = ahora.replace(second=0, microsecond=0) + timedelta(minutes=1)

        for _ in range(60 * 24 * 8):
            if candidato.minute in minutos and candidato.hour in horas:
                if dows is None or candidato.weekday() in [d % 7 for d in dows]:
                    if dom_p == "*" or candidato.day in _parse_field(dom_p, 31, 1):
                        if mes_p == "*" or candidato.month in _parse_field(mes_p, 12, 1):
                            return candidato.isoformat(timespec="minutes")
            candidato += timedelta(minutes=1)

        return None
    except Exception:
        return None
