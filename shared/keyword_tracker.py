"""
KeywordTracker - Tracking historico de rendimiento de keywords/tags
====================================================================

Acumula datos de rendimiento por keyword a lo largo del tiempo.
Cada vez que el tracker de performance (0.5) evalua un video en
T+7d o T+30d, registra las keywords del video con sus metricas.

Con el tiempo, esto permite saber:
  - Que keywords generan mas vistas/CTR/engagement
  - Cuales reusar en futuros videos
  - Cuales evitar

Almacena en SQLite (keyword_performance.db) con WAL mode.
"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .config import STORAGE_DIR

DB_PATH = Path(STORAGE_DIR) / "analytics" / "keyword_performance.db"

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


def _ensure_tables():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keyword_stats (
            keyword TEXT PRIMARY KEY,
            usos INTEGER DEFAULT 0,
            vistas_total INTEGER DEFAULT 0,
            vistas_promedio REAL DEFAULT 0,
            mejor_vistas INTEGER DEFAULT 0,
            mejor_video_id TEXT,
            mejor_titulo TEXT,
            ctr_promedio REAL,
            engagement_promedio REAL,
            ultimo_uso TEXT,
            actualizado_en TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keyword_video_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            video_id TEXT NOT NULL,
            proyecto_id TEXT,
            titulo TEXT,
            vistas INTEGER DEFAULT 0,
            ctr REAL,
            engagement_rate REAL,
            retencion REAL,
            score REAL,
            checkpoint TEXT,
            registrado_en TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_kw_video_keyword
        ON keyword_video_log(keyword)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_kw_video_video
        ON keyword_video_log(video_id)
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
            _ensure_tables()
            _table_ready = True


def registrar_keywords_video(
    keywords: list[str],
    video_id: str,
    proyecto_id: str | None = None,
    titulo: str | None = None,
    vistas: int = 0,
    ctr: float | None = None,
    engagement_rate: float | None = None,
    retencion: float | None = None,
    score: float | None = None,
    checkpoint: str | None = None,
):
    """Registra las keywords de un video con sus metricas de performance."""
    _init()
    conn = _get_conn()
    ahora = datetime.utcnow().isoformat(timespec="seconds")

    for kw in keywords:
        kw = kw.strip().lower()
        if not kw or len(kw) < 2:
            continue

        conn.execute(
            """INSERT INTO keyword_video_log
               (keyword, video_id, proyecto_id, titulo, vistas, ctr,
                engagement_rate, retencion, score, checkpoint, registrado_en)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (kw, video_id, proyecto_id, titulo, vistas, ctr,
             engagement_rate, retencion, score, checkpoint, ahora),
        )

        existing = conn.execute(
            "SELECT * FROM keyword_stats WHERE keyword = ?", (kw,)
        ).fetchone()

        if existing:
            new_usos = existing["usos"] + 1
            new_vistas_total = existing["vistas_total"] + vistas
            new_vistas_promedio = new_vistas_total / new_usos if new_usos > 0 else 0

            new_ctr_promedio = existing["ctr_promedio"]
            if ctr is not None:
                if new_ctr_promedio is not None:
                    new_ctr_promedio = ((new_ctr_promedio * existing["usos"]) + ctr) / new_usos
                else:
                    new_ctr_promedio = ctr

            new_eng_promedio = existing["engagement_promedio"]
            if engagement_rate is not None:
                if new_eng_promedio is not None:
                    new_eng_promedio = ((new_eng_promedio * existing["usos"]) + engagement_rate) / new_usos
                else:
                    new_eng_promedio = engagement_rate

            new_mejor_vistas = existing["mejor_vistas"]
            new_mejor_video = existing["mejor_video_id"]
            new_mejor_titulo = existing["mejor_titulo"]
            if vistas > new_mejor_vistas:
                new_mejor_vistas = vistas
                new_mejor_video = video_id
                new_mejor_titulo = titulo

            conn.execute(
                """UPDATE keyword_stats SET
                   usos = ?, vistas_total = ?, vistas_promedio = ?,
                   mejor_vistas = ?, mejor_video_id = ?, mejor_titulo = ?,
                   ctr_promedio = ?, engagement_promedio = ?,
                   ultimo_uso = ?, actualizado_en = ?
                   WHERE keyword = ?""",
                (new_usos, new_vistas_total, round(new_vistas_promedio, 1),
                 new_mejor_vistas, new_mejor_video, new_mejor_titulo,
                 round(new_ctr_promedio, 2) if new_ctr_promedio is not None else None,
                 round(new_eng_promedio, 2) if new_eng_promedio is not None else None,
                 ahora, ahora, kw),
            )
        else:
            conn.execute(
                """INSERT INTO keyword_stats
                   (keyword, usos, vistas_total, vistas_promedio,
                    mejor_vistas, mejor_video_id, mejor_titulo,
                    ctr_promedio, engagement_promedio, ultimo_uso, actualizado_en)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kw, 1, vistas, float(vistas),
                 vistas, video_id, titulo,
                 round(ctr, 2) if ctr is not None else None,
                 round(engagement_rate, 2) if engagement_rate is not None else None,
                 ahora, ahora),
            )

    conn.commit()


def top_keywords(
    limit: int = 30,
    ordenar_por: str = "vistas_promedio",
    min_usos: int = 1,
) -> list[dict]:
    """Devuelve las keywords con mejor rendimiento."""
    _init()
    conn = _get_conn()

    columnas_validas = {"vistas_promedio", "vistas_total", "ctr_promedio", "engagement_promedio", "usos", "mejor_vistas"}
    if ordenar_por not in columnas_validas:
        ordenar_por = "vistas_promedio"

    rows = conn.execute(
        f"""SELECT * FROM keyword_stats
            WHERE usos >= ?
            ORDER BY {ordenar_por} DESC NULLS LAST
            LIMIT ?""",
        (min_usos, limit),
    ).fetchall()

    return [dict(row) for row in rows]


def historial_keyword(keyword: str, limit: int = 20) -> list[dict]:
    """Devuelve el historial de un keyword especifico."""
    _init()
    conn = _get_conn()

    rows = conn.execute(
        """SELECT * FROM keyword_video_log
           WHERE keyword = ?
           ORDER BY registrado_en DESC
           LIMIT ?""",
        (keyword.strip().lower(), limit),
    ).fetchall()

    return [dict(row) for row in rows]


def stats() -> dict:
    """Estadisticas generales del keyword tracker."""
    _init()
    conn = _get_conn()

    total_kw = conn.execute("SELECT COUNT(*) FROM keyword_stats").fetchone()[0]
    total_registros = conn.execute("SELECT COUNT(*) FROM keyword_video_log").fetchone()[0]
    total_videos = conn.execute(
        "SELECT COUNT(DISTINCT video_id) FROM keyword_video_log"
    ).fetchone()[0]

    top_1 = conn.execute(
        "SELECT keyword, vistas_promedio FROM keyword_stats ORDER BY vistas_promedio DESC LIMIT 1"
    ).fetchone()

    return {
        "total_keywords": total_kw,
        "total_registros": total_registros,
        "total_videos_trackeados": total_videos,
        "mejor_keyword": dict(top_1) if top_1 else None,
    }
