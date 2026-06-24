"""
Health checks de credenciales y dependencias - YTCreator Studio
=================================================================

Valida que las API keys y dependencias locales funcionen ANTES de
gastar tiempo de pipeline. Cada check hace la llamada mas liviana
posible al servicio correspondiente.
"""

import shutil
from pathlib import Path

import httpx

from .config import (
    GROQ_API_KEY,
    HF_API_TOKEN,
    KAGGLE_KEY,
    KAGGLE_USERNAME,
    PIXABAY_API_KEY,
    SUBTITULOS_FONT_PATH,
    YOUTUBE_API_KEY,
    YOUTUBE_CLIENT_ID,
    YOUTUBE_CLIENT_SECRET,
    YOUTUBE_REFRESH_TOKEN,
)


class HealthCheckError(Exception):
    """Fallo en una o mas validaciones pre-pipeline."""

    def __init__(self, fallos: list[str]):
        self.fallos = fallos
        detalle = "; ".join(fallos)
        super().__init__(f"{len(fallos)} validacion(es) fallaron: {detalle}")


def check_groq() -> str | None:
    if not GROQ_API_KEY:
        return "GROQ_API_KEY no esta configurada en .env"
    try:
        from groq import Groq

        cliente = Groq(api_key=GROQ_API_KEY)
        cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        return None
    except Exception as exc:
        return f"GROQ_API_KEY invalida o Groq no responde: {exc}"


def check_hf() -> str | None:
    if not HF_API_TOKEN:
        return "HF_API_TOKEN no esta configurada en .env"
    try:
        resp = httpx.get(
            "https://huggingface.co/api/whoami-v2",
            headers={"Authorization": f"Bearer {HF_API_TOKEN}"},
            timeout=15,
        )
        if resp.status_code == 401:
            return "HF_API_TOKEN invalida (401 Unauthorized)"
        resp.raise_for_status()
        return None
    except httpx.HTTPStatusError as exc:
        return f"HF_API_TOKEN: error HTTP {exc.response.status_code}"
    except Exception as exc:
        return f"No se pudo conectar a Hugging Face: {exc}"


def check_kaggle() -> str | None:
    if not KAGGLE_USERNAME or not KAGGLE_KEY:
        return "KAGGLE_USERNAME y/o KAGGLE_KEY no estan configuradas en .env"
    try:
        import base64

        token = base64.b64encode(f"{KAGGLE_USERNAME}:{KAGGLE_KEY}".encode()).decode()
        resp = httpx.get(
            "https://www.kaggle.com/api/v1/kernels/list",
            headers={"Authorization": f"Basic {token}"},
            params={"pageSize": 1},
            timeout=15,
        )
        if resp.status_code == 401:
            return "KAGGLE_KEY invalida (401 Unauthorized)"
        resp.raise_for_status()
        return None
    except httpx.HTTPStatusError as exc:
        return f"Kaggle API: error HTTP {exc.response.status_code}"
    except Exception as exc:
        return f"No se pudo conectar a Kaggle: {exc}"


def check_pixabay() -> str | None:
    if not PIXABAY_API_KEY:
        return None
    try:
        resp = httpx.get(
            "https://pixabay.com/api/",
            params={"key": PIXABAY_API_KEY, "q": "test", "per_page": 3},
            timeout=10,
        )
        if resp.status_code == 401:
            return "PIXABAY_API_KEY invalida (401)"
        resp.raise_for_status()
        return None
    except Exception as exc:
        return f"No se pudo conectar a Pixabay: {exc}"


def check_font() -> str | None:
    if not SUBTITULOS_FONT_PATH:
        return "SUBTITULOS_FONT_PATH no esta configurada en .env"
    if not Path(SUBTITULOS_FONT_PATH).exists():
        return f"Fuente no encontrada: {SUBTITULOS_FONT_PATH}"
    return None


def check_ffmpeg() -> str | None:
    if not shutil.which("ffmpeg"):
        return "ffmpeg no encontrado en PATH (requerido por moviepy para renderizar video)"
    return None


def check_youtube_data_api() -> str | None:
    if not YOUTUBE_API_KEY and not all([YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN]):
        return "Se necesita YOUTUBE_API_KEY o credenciales OAuth2 completas para Channel Intelligence"
    return None


# ── Mapa fase -> checks necesarios ────────────────────────────────

CHECKS_POR_FASE: dict[str, list] = {
    "inteligencia": [check_youtube_data_api, check_groq],
    "estrategia": [check_groq, check_hf],
    "guion":      [check_groq],
    "visual":     [check_kaggle],
    "audio":      [check_hf, check_pixabay],
    "cierre":     [check_groq, check_font, check_ffmpeg],
}


def validar_fase(fase: str) -> None:
    checks = CHECKS_POR_FASE.get(fase, [])
    fallos = []
    for check_fn in checks:
        error = check_fn()
        if error:
            fallos.append(error)
    if fallos:
        raise HealthCheckError(fallos)


def validar_todo() -> None:
    ya_ejecutados = set()
    fallos = []
    for checks in CHECKS_POR_FASE.values():
        for check_fn in checks:
            if check_fn not in ya_ejecutados:
                ya_ejecutados.add(check_fn)
                error = check_fn()
                if error:
                    fallos.append(error)
    if fallos:
        raise HealthCheckError(fallos)
