"""
Gestor de estado de canales - YTCreator Studio
================================================

Cada canal conectado vive en channels/<canal_id>.json
Sigue el mismo patron que state_manager.py (FileLock, tmp+bak, recovery).
"""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from filelock import FileLock

from .config import STORAGE_DIR
from .schemas import EstadoCanal

CHANNELS_DIR = Path(STORAGE_DIR) / "channels"
CHANNELS_DIR.mkdir(parents=True, exist_ok=True)


class ChannelManager:
    def __init__(self, channels_dir: str | None = None):
        if channels_dir is None:
            channels_dir = str(CHANNELS_DIR)
        self.channels_dir = Path(channels_dir)
        self.channels_dir.mkdir(parents=True, exist_ok=True)

    def _json_path(self, canal_id: str) -> Path:
        return self.channels_dir / f"{canal_id}.json"

    def _tmp_path(self, canal_id: str) -> Path:
        return self.channels_dir / f"{canal_id}.tmp.json"

    def _bak_path(self, canal_id: str) -> Path:
        return self.channels_dir / f"{canal_id}.bak.json"

    def _lock_path(self, canal_id: str) -> Path:
        return self.channels_dir / f"{canal_id}.lock"

    def crear(self, canal_id: str, nombre: str) -> EstadoCanal:
        json_path = self._json_path(canal_id)
        if json_path.exists():
            return self.leer(canal_id)
        orden = self._proximo_orden()
        gpu_provider = self._asignar_gpu_provider(orden)
        estado = EstadoCanal(
            canal_id=canal_id,
            nombre=nombre,
            orden=orden,
            gpu_provider=gpu_provider,
        )
        self._escribir(estado)
        return estado

    def leer(self, canal_id: str) -> EstadoCanal:
        json_path = self._json_path(canal_id)
        bak_path = self._bak_path(canal_id)
        lock = FileLock(str(self._lock_path(canal_id)))
        with lock:
            if not json_path.exists() and not bak_path.exists():
                raise FileNotFoundError(f"No existe el canal '{canal_id}'")
            return self._leer_con_recovery(json_path, bak_path)

    def guardar(self, estado: EstadoCanal) -> EstadoCanal:
        lock = FileLock(str(self._lock_path(estado.canal_id)))
        with lock:
            self._escribir(estado)
        return estado

    def actualizar(self, canal_id: str, **cambios: Any) -> EstadoCanal:
        json_path = self._json_path(canal_id)
        bak_path = self._bak_path(canal_id)
        lock = FileLock(str(self._lock_path(canal_id)))
        with lock:
            if not json_path.exists() and not bak_path.exists():
                raise FileNotFoundError(f"No existe el canal '{canal_id}'")
            estado_actual = self._leer_con_recovery(json_path, bak_path)
            data = json.loads(estado_actual.model_dump_json())
            for clave, valor in cambios.items():
                if isinstance(valor, dict) and isinstance(data.get(clave), dict):
                    data[clave].update(valor)
                else:
                    data[clave] = valor
            estado = EstadoCanal(**data)
            self._escribir(estado)
            return estado

    def eliminar(self, canal_id: str) -> None:
        lock = FileLock(str(self._lock_path(canal_id)))
        with lock:
            for path in [self._json_path(canal_id), self._bak_path(canal_id), self._tmp_path(canal_id)]:
                if path.exists():
                    path.unlink()

    def listar_canales(self) -> list[dict]:
        canales = []
        for path in self.channels_dir.glob("*.json"):
            if path.name.startswith("_") or ".bak." in path.name or ".tmp." in path.name:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                canales.append({
                    "canal_id": data.get("canal_id", path.stem),
                    "nombre": data.get("nombre", ""),
                    "suscriptores": data.get("suscriptores"),
                    "video_count": data.get("video_count"),
                    "escaneado_en": data.get("escaneado_en"),
                    "nicho": data.get("perfil", {}).get("nicho_principal", ""),
                    "orden": data.get("orden"),
                    "gpu_provider": data.get("gpu_provider"),
                    "miniatura_url": data.get("miniatura_url"),
                    "vistas_totales": data.get("vistas_totales"),
                })
            except (json.JSONDecodeError, Exception):
                continue
        return canales

    def _proximo_orden(self) -> int:
        max_orden = 0
        for path in self.channels_dir.glob("*.json"):
            if path.name.startswith("_") or ".bak." in path.name or ".tmp." in path.name:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                orden = data.get("orden", 0)
                if orden > max_orden:
                    max_orden = orden
            except (json.JSONDecodeError, Exception):
                continue
        return max_orden + 1

    def _asignar_gpu_provider(self, orden: int) -> str:
        from .gpu_provider import proveedores_disponibles

        disponibles = proveedores_disponibles()

        if disponibles.get("kaggle") and not disponibles.get("modal") and not disponibles.get("beam"):
            return "kaggle"

        if disponibles.get("modal") and disponibles.get("beam"):
            return "modal" if orden % 2 == 1 else "beam"

        if disponibles.get("modal"):
            return "modal"

        if disponibles.get("beam"):
            return "beam"

        if disponibles.get("kaggle"):
            return "kaggle"

        return "kaggle"

    def canal_necesita_refresco(self, canal_id: str, max_horas: int = 24) -> bool:
        try:
            estado = self.leer(canal_id)
        except FileNotFoundError:
            return True
        if not estado.escaneado_en:
            return True
        desde_escaneo = datetime.utcnow() - estado.escaneado_en
        return desde_escaneo > timedelta(hours=max_horas)

    def _leer_con_recovery(self, json_path: Path, bak_path: Path) -> EstadoCanal:
        for path in [json_path, bak_path]:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                estado = EstadoCanal(**data)
                if path == bak_path:
                    self._escribir(estado)
                return estado
            except (json.JSONDecodeError, Exception):
                continue
        raise FileNotFoundError("No se pudo recuperar el canal (principal y backup corruptos)")

    def _escribir(self, estado: EstadoCanal) -> None:
        json_path = self._json_path(estado.canal_id)
        tmp_path = self._tmp_path(estado.canal_id)
        bak_path = self._bak_path(estado.canal_id)
        tmp_path.write_text(estado.model_dump_json(indent=2), encoding="utf-8")
        if json_path.exists():
            shutil.copy2(str(json_path), str(bak_path))
        os.replace(str(tmp_path), str(json_path))
