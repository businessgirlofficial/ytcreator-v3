"""
Cliente Kaggle compartido - YTCreator Studio
================================================

Wrapper sobre la API OFICIAL de Kaggle (paquete `kaggle`, version
2.2.2 verificada) para subir prompts, disparar la ejecucion remota
del notebook YouTube AI Studio v7, y descargar sus resultados.

Autenticacion: usa KAGGLE_USERNAME + KAGGLE_KEY (las mismas
credenciales de siempre, de https://www.kaggle.com/settings/api).
NO uses KAGGLE_API_TOKEN -- ese es un esquema OAuth distinto que esta
libreria no usa para estas operaciones; KAGGLE_KEY es el "API token"
clasico que generas en esa misma pagina.

IMPORTANTE: el paquete `kaggle` dispara su propio chequeo de
credenciales apenas se importa (no solo al llamar a authenticate()).
Por eso el import va DENTRO de _get_api(), nunca a nivel de modulo:
si estuviera arriba, todo el microservicio se caeria al arrancar
cuando falten las credenciales, en vez de arrancar bien y fallar
solo cuando alguien intente usarlo (el mismo patron que ya usamos
para GROQ_API_KEY)."""

import os

_api = None


def _get_api():
    global _api
    if _api is None:
        if not os.getenv("KAGGLE_USERNAME") or not os.getenv("KAGGLE_KEY"):
            raise RuntimeError(
                "KAGGLE_USERNAME y/o KAGGLE_KEY no estan configurados. "
                "Generalos en https://www.kaggle.com/settings/api y agregalos a tu .env."
            )
        from kaggle.api.kaggle_api_extended import KaggleApi  # import diferido, ver nota arriba

        api = KaggleApi()
        api.authenticate()
        _api = api
    return _api


def subir_dataset(folder: str, mensaje: str = "actualizacion automatica de prompts") -> None:
    """Sube una nueva version del dataset que el notebook lee como input.
    La carpeta debe contener dataset-metadata.json + los archivos a subir."""
    api = _get_api()
    api.dataset_create_version(folder, mensaje, dir_mode="zip")


def lanzar_kernel(folder: str) -> None:
    """Empuja el kernel y dispara su ejecucion remota en Kaggle.
    La carpeta debe contener kernel-metadata.json apuntando a tu notebook."""
    api = _get_api()
    api.kernels_push(folder)


def estado_kernel(kernel_slug: str) -> tuple[str, str | None]:
    """Devuelve (status, mensaje_de_error_si_aplica). status tipico:
    'running', 'queued', 'complete', 'error', 'cancelAcknowledged'."""
    api = _get_api()
    resultado = api.kernels_status(kernel_slug)
    return resultado.status, getattr(resultado, "failure_message", None)


def descargar_resultados(kernel_slug: str, destino: str) -> list[str]:
    """Descarga los archivos de salida de un kernel ya completado."""
    api = _get_api()
    archivos, _ = api.kernels_output(kernel_slug, path=destino)
    return archivos
