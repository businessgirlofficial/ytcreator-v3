"""
Cliente YouTube Data API v3 - YTCreator Studio
=================================================

Centraliza TODAS las llamadas a YouTube Data API con:
  - Tracking automatico de quota (10,000 units/dia gratis)
  - Cache en disco con TTL configurable
  - Soporte dual: OAuth2 (canal propio) + API Key (competidores)

Cada agente del Depto 0 usa este cliente en vez de hacer
llamadas directas a la API.
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from filelock import FileLock

from .config import (
    STORAGE_DIR,
    YOUTUBE_API_KEY,
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN,
)
from .logger import get_logger

log = get_logger("youtube_client")

CHANNELS_DIR = Path(STORAGE_DIR) / "channels"
CHANNELS_DIR.mkdir(parents=True, exist_ok=True)

CACHE_DIR = CHANNELS_DIR / "_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

QUOTA_PATH = CHANNELS_DIR / "_quota.json"
QUOTA_LOCK = CHANNELS_DIR / "_quota.lock"

QUOTA_LIMITE = int(__import__("os").getenv("YOUTUBE_QUOTA_LIMITE", "9000"))
CACHE_TTL_HORAS = int(__import__("os").getenv("CANAL_CACHE_TTL_HORAS", "24"))

UNIT_COSTS = {
    "channels.list": 1,
    "playlistItems.list": 1,
    "videos.list": 1,
    "search.list": 100,
}


class QuotaExcedidaError(Exception):
    pass


# ── Quota tracking ─────────────────────────────────────────────

def _leer_quota() -> dict:
    lock = FileLock(str(QUOTA_LOCK))
    with lock:
        if not QUOTA_PATH.exists():
            return {"fecha": datetime.utcnow().strftime("%Y-%m-%d"), "unidades_usadas": 0, "detalle": []}
        data = json.loads(QUOTA_PATH.read_text(encoding="utf-8"))
        if data.get("fecha") != datetime.utcnow().strftime("%Y-%m-%d"):
            return {"fecha": datetime.utcnow().strftime("%Y-%m-%d"), "unidades_usadas": 0, "detalle": []}
        return data


def _registrar_uso(operacion: str, unidades: int) -> None:
    lock = FileLock(str(QUOTA_LOCK))
    with lock:
        hoy = datetime.utcnow().strftime("%Y-%m-%d")
        if QUOTA_PATH.exists():
            data = json.loads(QUOTA_PATH.read_text(encoding="utf-8"))
            if data.get("fecha") != hoy:
                data = {"fecha": hoy, "unidades_usadas": 0, "detalle": []}
        else:
            data = {"fecha": hoy, "unidades_usadas": 0, "detalle": []}

        data["unidades_usadas"] += unidades
        data["detalle"].append({
            "operacion": operacion,
            "unidades": unidades,
            "hora": datetime.utcnow().strftime("%H:%M:%S"),
        })
        QUOTA_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    if data["unidades_usadas"] > 7000:
        log.warning("quota alta: %d/%d unidades usadas hoy", data["unidades_usadas"], QUOTA_LIMITE)


def _verificar_quota(unidades_necesarias: int) -> None:
    quota = _leer_quota()
    if quota["unidades_usadas"] + unidades_necesarias > QUOTA_LIMITE:
        raise QuotaExcedidaError(
            f"Quota insuficiente: {quota['unidades_usadas']}/{QUOTA_LIMITE} usadas, "
            f"necesita {unidades_necesarias} mas"
        )


def obtener_quota_hoy() -> dict:
    quota = _leer_quota()
    quota["limite"] = QUOTA_LIMITE
    quota["restante"] = max(0, QUOTA_LIMITE - quota["unidades_usadas"])
    return quota


# ── Cache ──────────────────────────────────────────────────────

def _cache_path(key: str) -> Path:
    safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
    return CACHE_DIR / f"{safe_key}.json"


def _cache_leer(key: str) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        guardado = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
        if datetime.utcnow() - guardado > timedelta(hours=CACHE_TTL_HORAS):
            return None
        return data
    except (json.JSONDecodeError, ValueError):
        return None


def _cache_escribir(key: str, data: dict) -> None:
    data["_cached_at"] = datetime.utcnow().isoformat()
    _cache_path(key).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── YouTube service builders ───────────────────────────────────

def _build_service_oauth():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    credentials.refresh(Request())
    return build("youtube", "v3", credentials=credentials)


def _build_service_apikey():
    from googleapiclient.discovery import build
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def _get_service(prefer_oauth: bool = False):
    if prefer_oauth and all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN]):
        return _build_service_oauth()
    if YOUTUBE_API_KEY:
        return _build_service_apikey()
    if all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN]):
        return _build_service_oauth()
    raise RuntimeError(
        "No hay credenciales YouTube configuradas. "
        "Configura YOUTUBE_API_KEY o las credenciales OAuth2 en .env"
    )


# ── Parseo de input de canal ──────────────────────────────────

def _extraer_channel_id(canal_input: str) -> str | None:
    """Intenta extraer un channel ID de una URL, handle o ID directo."""
    canal_input = canal_input.strip()

    if canal_input.startswith("UC") and len(canal_input) == 24:
        return canal_input

    match = re.search(r"youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})", canal_input)
    if match:
        return match.group(1)

    return None


def _extraer_handle(canal_input: str) -> str | None:
    canal_input = canal_input.strip()
    if canal_input.startswith("@"):
        return canal_input

    match = re.search(r"youtube\.com/@([a-zA-Z0-9_.-]+)", canal_input)
    if match:
        return f"@{match.group(1)}"

    return None


# ── API calls ──────────────────────────────────────────────────

def obtener_canal(canal_input: str) -> dict:
    """
    Obtiene metadata de un canal a partir de URL, @handle o channel ID.
    Retorna dict con: id, nombre, descripcion, suscriptores, video_count,
    vistas_totales, uploads_playlist_id, miniatura_url, banner_url.
    """
    channel_id = _extraer_channel_id(canal_input)
    handle = _extraer_handle(canal_input) if not channel_id else None

    cached = _cache_leer(f"canal_{channel_id or handle}")
    if cached:
        cached.pop("_cached_at", None)
        return cached

    _verificar_quota(1)
    service = _get_service()

    params = {
        "part": "snippet,statistics,contentDetails,brandingSettings",
        "maxResults": 1,
    }
    if channel_id:
        params["id"] = channel_id
    elif handle:
        params["forHandle"] = handle.lstrip("@")
    else:
        _verificar_quota(100)
        search_resp = service.search().list(
            part="snippet", q=canal_input, type="channel", maxResults=1
        ).execute()
        _registrar_uso("search.list", 100)
        items = search_resp.get("items", [])
        if not items:
            raise ValueError(f"No se encontro canal para: {canal_input}")
        params["id"] = items[0]["snippet"]["channelId"]

    resp = service.channels().list(**params).execute()
    _registrar_uso("channels.list", 1)

    items = resp.get("items", [])
    if not items:
        raise ValueError(f"Canal no encontrado: {canal_input}")

    ch = items[0]
    snippet = ch.get("snippet", {})
    stats = ch.get("statistics", {})
    content = ch.get("contentDetails", {})
    branding = ch.get("brandingSettings", {})

    resultado = {
        "id": ch["id"],
        "nombre": snippet.get("title", ""),
        "descripcion": snippet.get("description", ""),
        "suscriptores": int(stats.get("subscriberCount", 0)),
        "video_count": int(stats.get("videoCount", 0)),
        "vistas_totales": int(stats.get("viewCount", 0)),
        "uploads_playlist_id": content.get("relatedPlaylists", {}).get("uploads"),
        "miniatura_url": snippet.get("thumbnails", {}).get("high", {}).get("url"),
        "banner_url": branding.get("image", {}).get("bannerExternalUrl"),
        "creado_youtube": snippet.get("publishedAt"),
    }

    _cache_escribir(f"canal_{ch['id']}", resultado)
    return resultado


def obtener_videos_recientes(uploads_playlist_id: str, max_videos: int = 50) -> list[str]:
    """
    Obtiene los IDs de los videos mas recientes de un playlist de uploads.
    Usa playlistItems.list (1 unit/pagina) en vez de search.list (100 units).
    """
    cache_key = f"playlist_{uploads_playlist_id}"
    cached = _cache_leer(cache_key)
    if cached and cached.get("video_ids"):
        return cached["video_ids"][:max_videos]

    service = _get_service()
    video_ids = []
    page_token = None

    while len(video_ids) < max_videos:
        _verificar_quota(1)
        params = {
            "part": "contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": min(50, max_videos - len(video_ids)),
        }
        if page_token:
            params["pageToken"] = page_token

        resp = service.playlistItems().list(**params).execute()
        _registrar_uso("playlistItems.list", 1)

        for item in resp.get("items", []):
            vid_id = item.get("contentDetails", {}).get("videoId")
            if vid_id:
                video_ids.append(vid_id)

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    _cache_escribir(cache_key, {"video_ids": video_ids})
    return video_ids


def obtener_metricas_videos(video_ids: list[str]) -> list[dict]:
    """
    Obtiene metricas de una lista de videos en batches de 50 (1 unit/batch).
    Retorna lista de dicts con: video_id, titulo, publicado_en, vistas,
    likes, comentarios, duracion_seg, miniatura_url, tags, categoria_id.
    """
    if not video_ids:
        return []

    cache_key = f"metricas_{'_'.join(sorted(video_ids[:5]))}_{len(video_ids)}"
    cached = _cache_leer(cache_key)
    if cached and cached.get("videos"):
        return cached["videos"]

    service = _get_service()
    resultados = []

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        _verificar_quota(1)

        resp = service.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(batch),
        ).execute()
        _registrar_uso("videos.list", 1)

        for item in resp.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content = item.get("contentDetails", {})

            duracion_iso = content.get("duration", "PT0S")
            duracion_seg = _parsear_duracion_iso(duracion_iso)

            resultados.append({
                "video_id": item["id"],
                "titulo": snippet.get("title", ""),
                "publicado_en": snippet.get("publishedAt"),
                "vistas": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comentarios": int(stats.get("commentCount", 0)),
                "duracion_seg": duracion_seg,
                "miniatura_url": snippet.get("thumbnails", {}).get("high", {}).get("url"),
                "tags": snippet.get("tags", []),
                "categoria_id": snippet.get("categoryId"),
            })

    _cache_escribir(cache_key, {"videos": resultados})
    return resultados


def buscar_canales_relacionados(query: str, max_resultados: int = 5) -> list[dict]:
    """
    Busca canales por keyword. CARO: 100 units por llamada.
    Solo usar para discovery inicial de competidores.
    """
    _verificar_quota(100)
    service = _get_service()

    resp = service.search().list(
        part="snippet",
        q=query,
        type="channel",
        maxResults=max_resultados,
        order="relevance",
    ).execute()
    _registrar_uso("search.list", 100)

    canales = []
    for item in resp.get("items", []):
        snippet = item.get("snippet", {})
        canales.append({
            "channel_id": item["id"]["channelId"],
            "nombre": snippet.get("title", ""),
            "descripcion": snippet.get("description", ""),
        })

    return canales


# ── Helpers ────────────────────────────────────────────────────

def _parsear_duracion_iso(iso_duration: str) -> int:
    """Convierte ISO 8601 duration (PT1H2M3S) a segundos."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def credenciales_disponibles() -> bool:
    return bool(YOUTUBE_API_KEY) or all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN])


def oauth_disponible() -> bool:
    return all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN])


# ── YouTube Analytics API v2 ─────────────────────────────────

def _build_analytics_service():
    """YouTube Analytics API v2 — requiere OAuth (solo canal propio)."""
    if not oauth_disponible():
        raise RuntimeError(
            "YouTube Analytics API requiere OAuth2. "
            "Configura YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET y YOUTUBE_REFRESH_TOKEN."
        )
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    credentials.refresh(Request())
    return build("youtubeAnalytics", "v2", credentials=credentials)


def obtener_analytics_video(video_id: str, fecha_inicio: str, fecha_fin: str) -> dict:
    """
    Obtiene metricas de analytics para un video propio via YouTube Analytics API v2.
    Retorna: views, impressions, ctr, avg_view_duration, avg_view_percentage,
    estimated_minutes_watched.
    Las fechas deben ser formato YYYY-MM-DD.
    Costo quota: 1 unit por query (Analytics API tiene su propia quota separada).
    """
    cache_key = f"analytics_{video_id}_{fecha_inicio}_{fecha_fin}"
    cached = _cache_leer(cache_key)
    if cached:
        cached.pop("_cached_at", None)
        return cached

    service = _build_analytics_service()

    try:
        resp = service.reports().query(
            ids="channel==MINE",
            startDate=fecha_inicio,
            endDate=fecha_fin,
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
            filters=f"video=={video_id}",
        ).execute()

        row = resp.get("rows", [[0, 0, 0, 0]])[0]
        resultado = {
            "video_id": video_id,
            "vistas": int(row[0]),
            "tiempo_visto_min": float(row[1]),
            "duracion_vista_promedio_seg": float(row[2]),
            "retencion_promedio": float(row[3]),
        }
    except Exception as e:
        log.warning("analytics basico fallo para %s: %s — usando solo Data API", video_id, e)
        resultado = {
            "video_id": video_id,
            "vistas": 0, "tiempo_visto_min": 0,
            "duracion_vista_promedio_seg": 0, "retencion_promedio": 0,
        }

    _cache_escribir(cache_key, resultado)
    return resultado


def obtener_impressions_ctr(video_id: str, fecha_inicio: str, fecha_fin: str) -> dict:
    """CTR e impressions — solo disponible despues de ~48h de publicacion."""
    cache_key = f"ctr_{video_id}_{fecha_inicio}_{fecha_fin}"
    cached = _cache_leer(cache_key)
    if cached:
        cached.pop("_cached_at", None)
        return cached

    service = _build_analytics_service()

    try:
        resp = service.reports().query(
            ids="channel==MINE",
            startDate=fecha_inicio,
            endDate=fecha_fin,
            metrics="views,impressions,impressionClickThroughRate",
            filters=f"video=={video_id}",
        ).execute()

        row = resp.get("rows", [[0, 0, 0]])[0]
        resultado = {
            "video_id": video_id,
            "vistas": int(row[0]),
            "impressions": int(row[1]),
            "ctr": round(float(row[2]), 2),
        }
    except Exception as e:
        log.warning("impressions/ctr no disponible para %s: %s", video_id, e)
        resultado = {"video_id": video_id, "vistas": 0, "impressions": 0, "ctr": 0.0}

    _cache_escribir(cache_key, resultado)
    return resultado


def obtener_traffic_sources(video_id: str, fecha_inicio: str, fecha_fin: str) -> dict:
    """Fuentes de trafico — search, suggested, browse, external, otros."""
    service = _build_analytics_service()

    try:
        resp = service.reports().query(
            ids="channel==MINE",
            startDate=fecha_inicio,
            endDate=fecha_fin,
            metrics="views",
            dimensions="insightTrafficSourceType",
            filters=f"video=={video_id}",
        ).execute()

        total = 0
        raw = {}
        for row in resp.get("rows", []):
            source_type = row[0]
            views = int(row[1])
            raw[source_type] = views
            total += views

        if total == 0:
            return {"search": 0, "suggested": 0, "browse": 0, "external": 0, "otros": 0}

        mapping = {
            "YT_SEARCH": "search", "SUGGESTED": "suggested",
            "BROWSE": "browse", "EXT_URL": "external",
        }
        resultado = {"search": 0.0, "suggested": 0.0, "browse": 0.0, "external": 0.0, "otros": 0.0}
        for source_type, views in raw.items():
            key = mapping.get(source_type, "otros")
            resultado[key] += round((views / total) * 100, 1)

        return resultado
    except Exception as e:
        log.warning("traffic sources no disponible para %s: %s", video_id, e)
        return {"search": 0, "suggested": 0, "browse": 0, "external": 0, "otros": 0}


def obtener_demografia(video_id: str, fecha_inicio: str, fecha_fin: str) -> dict:
    """Top pais, edad y genero de la audiencia."""
    service = _build_analytics_service()
    resultado = {"top_pais": None, "top_edad": None, "top_genero": None}

    try:
        resp_age = service.reports().query(
            ids="channel==MINE",
            startDate=fecha_inicio,
            endDate=fecha_fin,
            metrics="viewerPercentage",
            dimensions="ageGroup",
            filters=f"video=={video_id}",
            sort="-viewerPercentage",
            maxResults=1,
        ).execute()
        rows = resp_age.get("rows", [])
        if rows:
            resultado["top_edad"] = rows[0][0]
    except Exception:
        pass

    try:
        resp_gender = service.reports().query(
            ids="channel==MINE",
            startDate=fecha_inicio,
            endDate=fecha_fin,
            metrics="viewerPercentage",
            dimensions="gender",
            filters=f"video=={video_id}",
            sort="-viewerPercentage",
            maxResults=1,
        ).execute()
        rows = resp_gender.get("rows", [])
        if rows:
            resultado["top_genero"] = rows[0][0]
    except Exception:
        pass

    try:
        resp_country = service.reports().query(
            ids="channel==MINE",
            startDate=fecha_inicio,
            endDate=fecha_fin,
            metrics="views",
            dimensions="country",
            filters=f"video=={video_id}",
            sort="-views",
            maxResults=1,
        ).execute()
        rows = resp_country.get("rows", [])
        if rows:
            resultado["top_pais"] = rows[0][0]
    except Exception:
        pass

    return resultado
