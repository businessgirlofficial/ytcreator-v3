"""
Utilidades de video compartidas - YTCreator Studio
======================================================

calcular_duraciones_por_palabras() reparte la duracion total de la
narracion entre las escenas, en proporcion a su cantidad de palabras.

Lo usan DOS agentes que deben coincidir exactamente:
  - Agente 5.1 (Editor): para saber cuanto dura cada clip/imagen
  - Agente 5.2 (Consultor SEO): para calcular los timestamps de los
    capitulos del video

Por eso vive en shared/ en vez de duplicarse en cada agente -- si los
capitulos no coinciden con el video real, es peor que no tener
capitulos.

Nota de diseno: no usamos los timestamps por palabra de Whisper
(Agente 4.3) para esto porque alinear el texto exacto de cada escena
contra las palabras transcritas es fragil (el TTS puede pronunciar o
normalizar el texto distinto a como esta escrito). Una division
proporcional por cantidad de palabras es mas simple y robusta, aunque
menos precisa que un alineamiento real palabra por palabra.
"""


def calcular_duraciones_por_palabras(escenas: list[dict], duracion_total: float) -> dict[int, float]:
    conteo_palabras = {e["numero"]: max(len(e["texto"].split()), 1) for e in escenas}
    total_palabras = sum(conteo_palabras.values()) or 1
    return {numero: duracion_total * (palabras / total_palabras) for numero, palabras in conteo_palabras.items()}
