"""
Agente 5.4 - Policy Monitor
Depto 5 (Cierre) - Ejecucion periodica, NO parte del pipeline

Verifica si las politicas oficiales de YouTube han cambiado desde la
ultima revision. Descarga el contenido de las URLs oficiales, calcula
un hash y lo compara contra knowledge/policies_checksums.json.

Si detecta cambios:
  - Reporta QUE fuentes cambiaron (URL + nombre)
  - NO modifica youtube_policies.md automaticamente (riesgo de meter
    basura por cambios de HTML)
  - Marca un warning para que el humano revise y actualice

Disenado para ejecutarse via n8n (semanal) o manualmente.
No bloquea ni interactua con el pipeline de videos.
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.config import REGISTRO_AGENTES
from shared.schemas import AgenteRequest, AgenteResponse
from shared.web_search import buscar

AGENTE_ID = "5.4_policy_monitor"
app: FastAPI = crear_agente_app(AGENTE_ID, descripcion="Monitorea cambios en politicas de YouTube")

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"
CHECKSUMS_PATH = KNOWLEDGE_DIR / "policies_checksums.json"


def _cargar_checksums() -> dict:
    if not CHECKSUMS_PATH.exists():
        raise FileNotFoundError(f"No se encontro {CHECKSUMS_PATH}")
    return json.loads(CHECKSUMS_PATH.read_text(encoding="utf-8"))


def _guardar_checksums(data: dict):
    CHECKSUMS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _obtener_contenido_pagina(url: str) -> str | None:
    """Busca la URL en DuckDuckGo y usa el snippet como proxy del contenido."""
    try:
        resultados = buscar(f"site:{url}", max_resultados=3)
        textos = [f"{r['titulo']} {r['resumen']}" for r in resultados]
        return " ".join(textos) if textos else None
    except Exception:
        return None


def _calcular_hash(contenido: str) -> str:
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def logica(request: AgenteRequest) -> dict:
    checksums = _cargar_checksums()
    fuentes = checksums.get("fuentes", {})
    cambios_detectados = []
    fuentes_verificadas = 0
    errores = []

    for nombre, info in fuentes.items():
        url = info.get("url", "")
        checksum_anterior = info.get("checksum")

        contenido = _obtener_contenido_pagina(url)
        if contenido is None:
            errores.append(f"No se pudo verificar: {nombre} ({url})")
            continue

        fuentes_verificadas += 1
        checksum_nuevo = _calcular_hash(contenido)

        if checksum_anterior is None:
            info["checksum"] = checksum_nuevo
            info["ultima_actualizacion"] = datetime.now().strftime("%Y-%m-%d")
        elif checksum_nuevo != checksum_anterior:
            cambios_detectados.append({
                "nombre": nombre,
                "url": url,
                "checksum_anterior": checksum_anterior[:12],
                "checksum_nuevo": checksum_nuevo[:12],
            })
            info["checksum"] = checksum_nuevo
            info["ultima_actualizacion"] = datetime.now().strftime("%Y-%m-%d")

    checksums["ultima_verificacion"] = datetime.now().strftime("%Y-%m-%d")
    _guardar_checksums(checksums)

    hay_cambios = len(cambios_detectados) > 0

    return {
        "hay_cambios": hay_cambios,
        "fuentes_verificadas": fuentes_verificadas,
        "cambios": cambios_detectados,
        "errores": errores,
        "mensaje": (
            f"ATENCION: Se detectaron cambios en {len(cambios_detectados)} fuente(s) "
            f"de politicas de YouTube. Revisar y actualizar knowledge/youtube_policies.md"
            if hay_cambios
            else f"Todo al dia: {fuentes_verificadas} fuentes verificadas sin cambios"
        ),
    }


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
