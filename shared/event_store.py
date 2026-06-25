"""
EventStore - Registro centralizado de eventos de automatizacion
=================================================================

Almacena eventos del sistema en SQLite para tener un historial
auditable y consultable de todo lo que pasa: pipelines lanzados,
agentes ejecutados, errores, publicaciones, health checks, etc.

Cada microservicio puede registrar eventos via la instancia global.
SQLite maneja concurrencia con WAL mode (multiples lectores, un
escritor a la vez sin bloqueo).
"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .config import STORAGE_DIR

DB_PATH = Path(STORAGE_DIR) / "events" / "automation_events.db"
_MAX_EVENTOS_DEFAULT = 200
_PURGE_DIAS_DEFAULT = 90

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def _ensure_table():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS automation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            source TEXT,
            proyecto_id TEXT,
            data TEXT,
            duration_seg REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_ts
        ON automation_events(timestamp DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_type
        ON automation_events(event_type)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_proyecto
        ON automation_events(proyecto_id)
    """)
    conn.commit()


_table_ready = False
_table_lock = threading.Lock()


def _init():
    global _table_ready
    if _table_ready:
        return
    with _table_lock:
        if not _table_ready:
            _ensure_table()
            _table_ready = True


def registrar(
    event_type: str,
    status: str,
    source: str | None = None,
    proyecto_id: str | None = None,
    data: dict | None = None,
    duration_seg: float | None = None,
) -> int:
    """Registra un evento y devuelve su ID."""
    import json

    _init()
    conn = _get_conn()
    ts = datetime.utcnow().isoformat(timespec="seconds")
    data_json = json.dumps(data, ensure_ascii=False, default=str) if data else None

    cursor = conn.execute(
        """INSERT INTO automation_events
           (timestamp, event_type, status, source, proyecto_id, data, duration_seg)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ts, event_type, status, source, proyecto_id, data_json, duration_seg),
    )
    conn.commit()
    return cursor.lastrowid


def consultar(
    limit: int = _MAX_EVENTOS_DEFAULT,
    event_type: str | None = None,
    status: str | None = None,
    proyecto_id: str | None = None,
    source: str | None = None,
    desde: str | None = None,
) -> list[dict]:
    """Consulta eventos con filtros opcionales, ordenados del mas reciente al mas viejo."""
    import json

    _init()
    conn = _get_conn()

    query = "SELECT * FROM automation_events WHERE 1=1"
    params: list = []

    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    if status:
        query += " AND status = ?"
        params.append(status)
    if proyecto_id:
        query += " AND proyecto_id = ?"
        params.append(proyecto_id)
    if source:
        query += " AND source = ?"
        params.append(source)
    if desde:
        query += " AND timestamp >= ?"
        params.append(desde)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    eventos = []
    for row in rows:
        evento = dict(row)
        if evento.get("data"):
            try:
                evento["data"] = json.loads(evento["data"])
            except (json.JSONDecodeError, TypeError):
                pass
        eventos.append(evento)
    return eventos


def contar(event_type: str | None = None, status: str | None = None) -> dict:
    """Devuelve conteos por tipo y estado."""
    _init()
    conn = _get_conn()

    total = conn.execute("SELECT COUNT(*) FROM automation_events").fetchone()[0]

    por_tipo = {}
    for row in conn.execute(
        "SELECT event_type, COUNT(*) as cnt FROM automation_events GROUP BY event_type"
    ).fetchall():
        por_tipo[row["event_type"]] = row["cnt"]

    por_status = {}
    for row in conn.execute(
        "SELECT status, COUNT(*) as cnt FROM automation_events GROUP BY status"
    ).fetchall():
        por_status[row["status"]] = row["cnt"]

    return {"total": total, "por_tipo": por_tipo, "por_status": por_status}


def purgar(dias: int = _PURGE_DIAS_DEFAULT) -> int:
    """Elimina eventos mas viejos que N dias. Devuelve cantidad eliminada."""
    _init()
    conn = _get_conn()

    cutoff = datetime.utcnow()
    cutoff = cutoff.replace(
        day=cutoff.day,
        hour=0, minute=0, second=0, microsecond=0,
    )
    from datetime import timedelta
    cutoff = cutoff - timedelta(days=dias)
    cutoff_str = cutoff.isoformat(timespec="seconds")

    cursor = conn.execute(
        "DELETE FROM automation_events WHERE timestamp < ?",
        (cutoff_str,),
    )
    conn.commit()
    return cursor.rowcount
