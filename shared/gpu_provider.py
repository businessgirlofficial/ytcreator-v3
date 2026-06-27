"""GPU provider availability check."""

from .config import KAGGLE_USERNAME, KAGGLE_KEY, MODAL_TOKEN_ID, MODAL_TOKEN_SECRET, BEAM_API_KEY


def proveedores_disponibles() -> dict[str, bool]:
    return {
        "kaggle": bool(KAGGLE_USERNAME and KAGGLE_KEY),
        "modal": bool(MODAL_TOKEN_ID and MODAL_TOKEN_SECRET),
        "beam": bool(BEAM_API_KEY),
    }
