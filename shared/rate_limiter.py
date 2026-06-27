"""
Rate Limiter global con Token Bucket - YTCreator Studio
==========================================================

Coordina el rate limiting entre TODOS los microservicios (procesos
separados) usando un archivo JSON compartido + FileLock. Esto es
critico porque nuestros 25 agentes corren como procesos uvicorn
independientes -- un lock en memoria solo serviria dentro de un
proceso.

Cada API externa tiene su propia instancia con limites configurados:
  - Groq: 30 RPM free tier → 24 RPM efectivos (margen 20%)
  - HuggingFace: ~10 RPM → 8 RPM efectivos
  - Pixabay: 50 RPH → ~0.67 RPM efectivos

El token bucket NUNCA falla por rate limit: simplemente espera hasta
que haya tokens disponibles. Los errores 429 se previenen en vez de
reaccionar a ellos.
"""

import json
import os
import time
from pathlib import Path

from filelock import FileLock

from .config import CLAUDE_RATE_LIMIT, GROQ_RATE_LIMIT, HF_RATE_LIMIT, PIXABAY_RATE_LIMIT, RATE_LIMIT_SAFETY_FACTOR, STORAGE_DIR
from .logger import get_logger

log = get_logger("rate_limiter")

RATE_LIMIT_DIR = Path(STORAGE_DIR) / "rate_limits"


class TokenBucketRateLimiter:
    """Token Bucket cross-process con archivo JSON + FileLock."""

    def __init__(
        self,
        nombre: str,
        requests_por_minuto: float,
        margen_seguridad: float = 0.8,
        burst_max: int = 4,
    ):
        self.nombre = nombre
        self.rpm_real = requests_por_minuto
        self.rpm_efectivo = requests_por_minuto * margen_seguridad
        self.tokens_por_segundo = self.rpm_efectivo / 60.0
        self.burst_max = min(burst_max, int(self.rpm_efectivo))
        self.capacidad = self.rpm_efectivo

        RATE_LIMIT_DIR.mkdir(parents=True, exist_ok=True)
        self._state_path = RATE_LIMIT_DIR / f"{nombre}.json"
        self._lock_path = RATE_LIMIT_DIR / f"{nombre}.lock"

        self._total_llamadas = 0
        self._total_esperas = 0
        self._total_segundos_esperados = 0.0

    def esperar(self) -> None:
        """Espera hasta que haya un token disponible y lo consume."""
        self._total_llamadas += 1

        while True:
            lock = FileLock(str(self._lock_path))
            with lock:
                ahora = time.time()
                estado = self._leer_estado()

                transcurrido = ahora - estado["ultimo_refill"]
                tokens_nuevos = transcurrido * self.tokens_por_segundo
                tokens_actuales = min(
                    estado["tokens"] + tokens_nuevos,
                    self.burst_max,
                )

                if tokens_actuales >= 1.0:
                    estado["tokens"] = tokens_actuales - 1.0
                    estado["ultimo_refill"] = ahora
                    estado["total_consumidos"] = estado.get("total_consumidos", 0) + 1
                    self._escribir_estado(estado)
                    return

                espera = (1.0 - tokens_actuales) / self.tokens_por_segundo
                estado["tokens"] = tokens_actuales
                estado["ultimo_refill"] = ahora
                self._escribir_estado(estado)

            self._total_esperas += 1
            self._total_segundos_esperados += espera
            pct = (self._total_esperas / self._total_llamadas * 100) if self._total_llamadas else 0
            promedio = self._total_segundos_esperados / self._total_esperas if self._total_esperas else 0
            log.info(
                "[%s] Token adquirido tras %.1fs de espera "
                "(stats: %d esperas, %.1fs total acumulado, %d llamadas)",
                self.nombre,
                espera,
                self._total_esperas,
                self._total_segundos_esperados,
                self._total_llamadas,
            )
            time.sleep(espera)

    def log_estadisticas(self) -> None:
        """Imprime un resumen de estadisticas al log."""
        if self._total_llamadas == 0:
            return
        pct = self._total_esperas / self._total_llamadas * 100
        promedio = self._total_segundos_esperados / self._total_esperas if self._total_esperas else 0
        log.info(
            "[%s] Stats — llamadas: %d, esperas: %d (%.1f%%), "
            "tiempo perdido: %.1fs, promedio espera: %.2fs",
            self.nombre,
            self._total_llamadas,
            self._total_esperas,
            pct,
            self._total_segundos_esperados,
            promedio,
        )

    @property
    def estadisticas(self) -> dict:
        """Estadisticas de este proceso (no globales cross-process)."""
        pct = (self._total_esperas / self._total_llamadas * 100) if self._total_llamadas else 0
        promedio = self._total_segundos_esperados / self._total_esperas if self._total_esperas else 0
        return {
            "nombre": self.nombre,
            "rpm_real": self.rpm_real,
            "rpm_efectivo": self.rpm_efectivo,
            "burst_max": self.burst_max,
            "llamadas": self._total_llamadas,
            "esperas": self._total_esperas,
            "esperas_pct": round(pct, 1),
            "tiempo_perdido_seg": round(self._total_segundos_esperados, 2),
            "promedio_espera_seg": round(promedio, 2),
        }

    def _leer_estado(self) -> dict:
        if self._state_path.exists():
            try:
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                if "tokens" in data and "ultimo_refill" in data:
                    return data
            except (json.JSONDecodeError, KeyError):
                pass
        return {
            "tokens": float(self.burst_max),
            "ultimo_refill": time.time(),
            "total_consumidos": 0,
        }

    def _escribir_estado(self, estado: dict) -> None:
        tmp_path = self._state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(estado), encoding="utf-8")
        os.replace(str(tmp_path), str(self._state_path))


# -- Instancias pre-configuradas por API ------------------------------------

GROQ_LIMITER = TokenBucketRateLimiter(
    nombre="groq",
    requests_por_minuto=GROQ_RATE_LIMIT,
    margen_seguridad=RATE_LIMIT_SAFETY_FACTOR,
    burst_max=4,
)

HF_LIMITER = TokenBucketRateLimiter(
    nombre="huggingface",
    requests_por_minuto=HF_RATE_LIMIT,
    margen_seguridad=RATE_LIMIT_SAFETY_FACTOR,
    burst_max=3,
)

PIXABAY_LIMITER = TokenBucketRateLimiter(
    nombre="pixabay",
    requests_por_minuto=PIXABAY_RATE_LIMIT,
    margen_seguridad=RATE_LIMIT_SAFETY_FACTOR,
    burst_max=2,
)

CLAUDE_LIMITER = TokenBucketRateLimiter(
    nombre="claude",
    requests_por_minuto=CLAUDE_RATE_LIMIT,
    margen_seguridad=RATE_LIMIT_SAFETY_FACTOR,
    burst_max=2,
)
