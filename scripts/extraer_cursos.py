"""
Extractor de cursos Hotmart → Texto
=====================================

Descarga el audio de videos de Hotmart usando yt-dlp + cookies de sesion,
los transcribe con Whisper, y genera archivos .txt limpios.

PREREQUISITOS:
    pip install yt-dlp openai-whisper

PREPARACION:
    1. Instala la extension "Get cookies.txt LOCALLY" en Chrome
       (https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
    2. Entra a Hotmart y logueate en tu cuenta
    3. Estando en cualquier pagina de Hotmart, click en la extension
       → "Export" → guarda el archivo como cookies.txt
    4. Pon ese archivo en: scripts/cookies.txt

USO:
    1. Edita la lista CURSOS al final de este archivo con las URLs
       de cada video
    2. Ejecuta:  python scripts/extraer_cursos.py
    3. Los .txt quedan en: cursos_extraidos/<nombre_curso>/

NOTAS:
    - Whisper modelo "base" es rapido pero menos preciso. Si tienes
      GPU y tiempo, cambia WHISPER_MODEL a "medium" o "large"
    - Si un video falla, el script continua con el siguiente y
      reporta los errores al final
"""

import os
import re
import subprocess
import sys
from pathlib import Path

WHISPER_MODEL = "base"
COOKIES_FILE = Path(__file__).parent / "cookies.txt"
OUTPUT_BASE = Path(__file__).resolve().parents[1] / "cursos_extraidos"
AUDIO_TEMP = OUTPUT_BASE / "_audio_temp"


def verificar_dependencias():
    faltantes = []
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        faltantes.append("yt-dlp  →  pip install yt-dlp")

    try:
        import whisper  # noqa: F401
    except ImportError:
        faltantes.append("whisper →  pip install openai-whisper")

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except FileNotFoundError:
        faltantes.append("ffmpeg  →  winget install Gyan.FFmpeg")

    if faltantes:
        print("ERROR: Faltan dependencias:")
        for f in faltantes:
            print(f"  - {f}")
        sys.exit(1)

    if not COOKIES_FILE.exists():
        print(f"ERROR: No se encontro {COOKIES_FILE}")
        print("Exporta las cookies de Hotmart con la extension 'Get cookies.txt LOCALLY'")
        print(f"y guardalas en: {COOKIES_FILE}")
        sys.exit(1)


def sanitizar_nombre(nombre: str) -> str:
    nombre = re.sub(r'[<>:"/\\|?*]', '_', nombre)
    nombre = re.sub(r'_+', '_', nombre).strip('_ ')
    return nombre[:80]


def descargar_audio(url: str, destino: Path) -> Path | None:
    destino.mkdir(parents=True, exist_ok=True)
    archivo_salida = destino / "audio.mp3"

    if archivo_salida.exists() and archivo_salida.stat().st_size > 10000:
        print(f"    [CACHE] Audio ya descargado, saltando...")
        return archivo_salida

    cmd = [
        "yt-dlp",
        "--cookies", str(COOKIES_FILE),
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "5",
        "-o", str(destino / "audio.%(ext)s"),
        "--no-warnings",
        "--no-playlist",
        url,
    ]

    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if resultado.returncode != 0:
            print(f"    [ERROR] yt-dlp fallo: {resultado.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print(f"    [ERROR] Timeout descargando audio")
        return None

    if archivo_salida.exists():
        return archivo_salida

    mp3s = list(destino.glob("*.mp3"))
    if mp3s:
        mp3s[0].rename(archivo_salida)
        return archivo_salida

    print(f"    [ERROR] No se genero archivo MP3")
    return None


def transcribir(audio_path: Path) -> str:
    txt_cache = audio_path.with_suffix(".txt")
    if txt_cache.exists() and txt_cache.stat().st_size > 0:
        print(f"    [CACHE] Transcripcion ya existe, saltando...")
        return txt_cache.read_text(encoding="utf-8")

    import whisper

    print(f"    [WHISPER] Transcribiendo con modelo '{WHISPER_MODEL}'...")
    modelo = whisper.load_model(WHISPER_MODEL)
    resultado = modelo.transcribe(
        str(audio_path),
        language="es",
        fp16=False,
    )
    texto = resultado["text"].strip()

    txt_cache.write_text(texto, encoding="utf-8")
    return texto


def procesar_curso(nombre_curso: str, videos: list[dict]):
    print(f"\n{'='*60}")
    print(f"CURSO: {nombre_curso}")
    print(f"{'='*60}")

    carpeta_curso = OUTPUT_BASE / sanitizar_nombre(nombre_curso)
    carpeta_curso.mkdir(parents=True, exist_ok=True)

    resultados = []
    errores = []

    for i, video in enumerate(videos, 1):
        titulo = video.get("titulo", f"video_{i}")
        url = video["url"]
        nombre_limpio = sanitizar_nombre(titulo)

        print(f"\n  [{i}/{len(videos)}] {titulo}")
        print(f"    URL: {url[:80]}...")

        carpeta_audio = AUDIO_TEMP / sanitizar_nombre(nombre_curso) / nombre_limpio

        audio_path = descargar_audio(url, carpeta_audio)
        if audio_path is None:
            errores.append(f"{titulo}: fallo la descarga")
            continue

        try:
            texto = transcribir(audio_path)
        except Exception as exc:
            errores.append(f"{titulo}: fallo la transcripcion — {exc}")
            continue

        archivo_txt = carpeta_curso / f"{i:02d}_{nombre_limpio}.txt"
        contenido = f"# {titulo}\n# Curso: {nombre_curso}\n\n{texto}\n"
        archivo_txt.write_text(contenido, encoding="utf-8")

        resultados.append(archivo_txt)
        print(f"    [OK] → {archivo_txt.name} ({len(texto)} chars)")

    resumen = carpeta_curso / "_resumen.txt"
    lineas = [f"Curso: {nombre_curso}", f"Videos procesados: {len(resultados)}/{len(videos)}", ""]
    for r in resultados:
        lineas.append(f"  - {r.name}")
    if errores:
        lineas.append(f"\nErrores ({len(errores)}):")
        for e in errores:
            lineas.append(f"  ! {e}")
    resumen.write_text("\n".join(lineas), encoding="utf-8")

    print(f"\n  Resumen: {len(resultados)}/{len(videos)} videos transcritos")
    if errores:
        print(f"  Errores: {len(errores)}")
        for e in errores:
            print(f"    ! {e}")

    return resultados, errores


# =====================================================================
# CONFIGURACION DE CURSOS
# =====================================================================
# Edita esta lista con las URLs de cada video.
# Puedes agregar tantos cursos como quieras.
#
# Formato:
#   {"titulo": "Nombre de la clase", "url": "https://..."}
#
# Para obtener la URL de cada video:
#   - Abre el video en Hotmart
#   - Copia la URL de la barra de direcciones
# =====================================================================

CURSOS = [
    {
        "nombre": "Monetizatube",
        "videos": [
            # {"titulo": "Clase 1 - Creacion del canal", "url": "https://..."},
            # {"titulo": "Clase 2 - Elige un buen nicho", "url": "https://..."},
            # ... agrega todas las clases aqui
        ],
    },
    # {
    #     "nombre": "Curso 2",
    #     "videos": [
    #         {"titulo": "...", "url": "https://..."},
    #     ],
    # },
]


if __name__ == "__main__":
    verificar_dependencias()

    if not any(curso["videos"] for curso in CURSOS):
        print("No hay videos configurados.")
        print("Edita la lista CURSOS en este archivo con las URLs de cada video.")
        print(f"Archivo: {__file__}")
        sys.exit(0)

    todos_resultados = []
    todos_errores = []

    for curso in CURSOS:
        if not curso["videos"]:
            continue
        r, e = procesar_curso(curso["nombre"], curso["videos"])
        todos_resultados.extend(r)
        todos_errores.extend(e)

    print(f"\n{'='*60}")
    print(f"COMPLETADO")
    print(f"  Videos transcritos: {len(todos_resultados)}")
    print(f"  Errores: {len(todos_errores)}")
    print(f"  Archivos en: {OUTPUT_BASE}")
    print(f"{'='*60}")
