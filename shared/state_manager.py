"""
Gestor de estado compartido - YTCreator Studio
================================================

Cada proyecto vive en projects/<proyecto_id>.json
Ese archivo es la "memoria" que todos los agentes leen y escriben.

El FileLock evita que dos agentes escriban al mismo tiempo y se
pisen los cambios entre si (condicion de carrera). Esto es critico
porque en el sistema hibrido varios agentes pueden estar trabajando
sobre el mismo proyecto en paralelo (ej. Audio y Visual a la vez).
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from filelock import FileLock

from .config import STORAGE_DIR
from .schemas import EstadoProyecto


class StateManager:
    def __init__(self, projects_dir: str | None = None):
        if projects_dir is None:
            projects_dir = str(Path(STORAGE_DIR) / "projects")
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    # -- rutas internas ----------------------------------------------------
    def _json_path(self, proyecto_id: str) -> Path:
        return self.projects_dir / f"{proyecto_id}.json"

    def _tmp_path(self, proyecto_id: str) -> Path:
        return self.projects_dir / f"{proyecto_id}.tmp.json"

    def _bak_path(self, proyecto_id: str) -> Path:
        return self.projects_dir / f"{proyecto_id}.bak.json"

    def _lock_path(self, proyecto_id: str) -> Path:
        return self.projects_dir / f"{proyecto_id}.lock"

    # -- operaciones publicas ------------------------------------------------
    def crear(self, proyecto_id: str, canal: str) -> EstadoProyecto:
        json_path = self._json_path(proyecto_id)
        if json_path.exists():
            raise FileExistsError(f"El proyecto '{proyecto_id}' ya existe")
        ahora = datetime.utcnow()
        estado = EstadoProyecto(
            proyecto_id=proyecto_id,
            canal=canal,
            creado_en=ahora,
            actualizado_en=ahora,
        )
        self._escribir(estado)
        return estado

    def leer(self, proyecto_id: str) -> EstadoProyecto:
        json_path = self._json_path(proyecto_id)
        bak_path = self._bak_path(proyecto_id)
        lock = FileLock(str(self._lock_path(proyecto_id)))
        with lock:
            if not json_path.exists() and not bak_path.exists():
                raise FileNotFoundError(f"No existe el proyecto '{proyecto_id}'")
            return self._leer_con_recovery(json_path, bak_path)

    def guardar(self, estado: EstadoProyecto) -> EstadoProyecto:
        """Reemplaza el estado completo. Usalo cuando ya tengas el objeto entero en memoria."""
        lock = FileLock(str(self._lock_path(estado.proyecto_id)))
        with lock:
            self._escribir(estado)
        return estado

    def actualizar(self, proyecto_id: str, **cambios: Any) -> EstadoProyecto:
        """
        Actualizacion parcial y segura. Ejemplo de uso real dentro de un agente:

            state.actualizar(
                "proy_123",
                estrategia={"titulo_ganador": "Como ahorre $1000 en un mes"}
            )

        Si el campo es un dict anidado (como 'estrategia' o 'guion'), se
        MEZCLA con lo que ya existia en vez de sobrescribir todo el bloque.
        Las listas (como 'escenas') se reemplazan completas, no se mezclan.
        """
        json_path = self._json_path(proyecto_id)
        bak_path = self._bak_path(proyecto_id)
        lock = FileLock(str(self._lock_path(proyecto_id)))
        with lock:
            if not json_path.exists() and not bak_path.exists():
                raise FileNotFoundError(f"No existe el proyecto '{proyecto_id}'")
            estado_actual = self._leer_con_recovery(json_path, bak_path)
            data = json.loads(estado_actual.model_dump_json())
            for clave, valor in cambios.items():
                if isinstance(valor, dict) and isinstance(data.get(clave), dict):
                    data[clave].update(valor)
                else:
                    data[clave] = valor
            estado = EstadoProyecto(**data)
            estado.actualizado_en = datetime.utcnow()
            self._escribir(estado)
            return estado

    def registrar_resultado_agente(self, proyecto_id: str, resultado: dict) -> None:
        """Agrega una entrada al historial de auditoria sin tocar el resto del estado."""
        json_path = self._json_path(proyecto_id)
        bak_path = self._bak_path(proyecto_id)
        lock = FileLock(str(self._lock_path(proyecto_id)))
        with lock:
            estado = self._leer_con_recovery(json_path, bak_path)
            data = json.loads(estado.model_dump_json())
            data.setdefault("historial_agentes", []).append(resultado)
            data["actualizado_en"] = datetime.utcnow().isoformat()
            estado = EstadoProyecto(**data)
            self._escribir(estado)

    def listar_proyectos(self) -> list[str]:
        return [p.stem for p in self.projects_dir.glob("*.json")]

    # -- interno --------------------------------------------------------------
    def _leer_con_recovery(self, json_path: Path, bak_path: Path) -> EstadoProyecto:
        for path in [json_path, bak_path]:
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                estado = EstadoProyecto(**data)
                if path == bak_path:
                    self._escribir(estado)
                return estado
            except (json.JSONDecodeError, Exception):
                continue
        raise FileNotFoundError(f"No se pudo recuperar el proyecto (principal y backup corruptos)")

    def _escribir(self, estado: EstadoProyecto) -> None:
        json_path = self._json_path(estado.proyecto_id)
        tmp_path = self._tmp_path(estado.proyecto_id)
        bak_path = self._bak_path(estado.proyecto_id)
        tmp_path.write_text(estado.model_dump_json(indent=2), encoding="utf-8")
        if json_path.exists():
            shutil.copy2(str(json_path), str(bak_path))
        os.replace(str(tmp_path), str(json_path))
