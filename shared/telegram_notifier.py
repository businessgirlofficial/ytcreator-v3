"""
Notificaciones Telegram - YTCreator Studio
=============================================

Modulo centralizado para enviar notificaciones de progreso del pipeline
via Telegram Bot API. Cada funcion publica es fire-and-forget: si
Telegram no esta disponible o no esta configurado, el pipeline
continua sin interrupcion.

Uso desde el orquestador:

    from shared import telegram_notifier as telegram

    telegram.notificar_inicio(proyecto_id, nicho, canal)
    telegram.notificar_fase("estrategia", proyecto_id, estado, duracion)
    telegram.notificar_completado(proyecto_id, estado, duracion, tiempos)
    telegram.notificar_error(proyecto_id, "guion", "rate limit", duracion)
"""

import html

import httpx

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_NOTIFICATIONS, \
    TELEGRAM_PC_LABEL
from .logger import get_logger
from .schemas import EstadoProyecto

log = get_logger("telegram")

_ETAPAS = ["estrategia", "guion", "visual", "audio", "cierre"]
_NOMBRES = {
    "estrategia": "Estrategia",
    "guion": "Guión",
    "visual": "Visual",
    "audio": "Audio",
    "cierre": "Cierre",
}


def _habilitado() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and TELEGRAM_NOTIFICATIONS)


def _pc() -> str:
    return f"[{TELEGRAM_PC_LABEL}] " if TELEGRAM_PC_LABEL else ""


def _enviar(mensaje: str) -> bool:
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": mensaje,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            log.warning("telegram HTTP %d: %s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as exc:
        log.warning("telegram no disponible: %s", exc)
        return False


def _e(texto) -> str:
    return html.escape(str(texto)) if texto else ""


def _dur(seg: float) -> str:
    if seg < 60:
        return f"{seg:.1f}s"
    m = int(seg // 60)
    s = seg % 60
    return f"{m}m {s:.0f}s"


def _progreso(fase_completada: str) -> str:
    if fase_completada not in _ETAPAS:
        return ""
    idx = _ETAPAS.index(fase_completada)
    partes = []
    for i, etapa in enumerate(_ETAPAS):
        nombre = _NOMBRES[etapa]
        partes.append(f"{'✅' if i <= idx else '⬜'} {nombre}")
    return " → ".join(partes)


# ── Funciones publicas (fire-and-forget) ────────────────────────


def notificar_inicio(proyecto_id: str, nicho: str, canal: str):
    if not _habilitado():
        return
    try:
        msg = (
            f"{_pc()}🚀 <b>PIPELINE INICIADO</b>\n"
            f"📁 <code>{_e(proyecto_id)}</code> · 📺 {_e(canal)}\n"
            f"🎯 Nicho: {_e(nicho)}\n\n"
            f"⬜ Estrategia → ⬜ Guión → ⬜ Visual → ⬜ Audio → ⬜ Cierre"
        )
        _enviar(msg)
    except Exception as exc:
        log.warning("telegram notificar_inicio: %s", exc)


def notificar_fase(
    fase: str,
    proyecto_id: str,
    estado: EstadoProyecto,
    duracion_seg: float,
):
    if not _habilitado():
        return
    try:
        nombre = _NOMBRES.get(fase, fase).upper()
        header = (
            f"{_pc()}✅ <b>{nombre} COMPLETADA</b>\n"
            f"📁 <code>{_e(proyecto_id)}</code> · ⏱ {_dur(duracion_seg)}\n"
        )
        detalles = _detalles(fase, estado)
        prog = _progreso(fase)
        _enviar(header + "\n" + detalles + "\n" + prog)
    except Exception as exc:
        log.warning("telegram notificar_fase(%s): %s", fase, exc)


def notificar_completado(
    proyecto_id: str,
    estado: EstadoProyecto,
    duracion_total: float,
    tiempos_fases: dict[str, float],
):
    if not _habilitado():
        return
    try:
        msg = _resumen_final(proyecto_id, estado, duracion_total, tiempos_fases)
        _enviar(msg)
    except Exception as exc:
        log.warning("telegram notificar_completado: %s", exc)


def notificar_error(
    proyecto_id: str,
    fase: str,
    error: str,
    duracion_seg: float,
):
    if not _habilitado():
        return
    try:
        nombre = _NOMBRES.get(fase, fase)
        msg = (
            f"{_pc()}❌ <b>ERROR EN PIPELINE</b>\n"
            f"📁 <code>{_e(proyecto_id)}</code>\n"
            f"📍 Fase: {nombre}\n"
            f"⏱ Falló después de: {_dur(duracion_seg)}\n\n"
            f"💬 {_e(str(error)[:500])}"
        )
        _enviar(msg)
    except Exception as exc:
        log.warning("telegram notificar_error: %s", exc)


# ── Extractores de detalles por fase ────────────────────────────


def _detalles(fase: str, estado: EstadoProyecto) -> str:
    extractores = {
        "estrategia": _det_estrategia,
        "guion": _det_guion,
        "visual": _det_visual,
        "audio": _det_audio,
        "cierre": _det_cierre,
    }
    fn = extractores.get(fase)
    return fn(estado) if fn else ""


def _det_estrategia(estado: EstadoProyecto) -> str:
    e = estado.estrategia
    lineas = []
    if e.titulo_ganador:
        lineas.append(f'📝 Título: "{_e(e.titulo_ganador)}"')
    if e.titulo_score is not None:
        lineas.append(f"📊 Score: {e.titulo_score}/10")
    if e.titulo_subcampeon:
        lineas.append(f'🥈 Subcampeón: "{_e(e.titulo_subcampeon)}"')
    if e.miniatura_path:
        lineas.append("🖼 Miniatura: generada")
    if e.mood:
        lineas.append(f"🎵 Mood: {_e(e.mood)}")
    return "\n".join(lineas) + "\n" if lineas else ""


def _det_guion(estado: EstadoProyecto) -> str:
    g = estado.guion
    lineas = []
    n = len(g.escenas)
    if n:
        s = f" · Score: {g.score}/100" if g.score is not None else ""
        lineas.append(f"🎬 {n} escenas{s}")
    hook = next((e for e in g.escenas if e.tipo == "hook"), None)
    if hook and hook.texto:
        preview = hook.texto[:80] + ("..." if len(hook.texto) > 80 else "")
        lineas.append(f'🎣 Hook: "{_e(preview)}"')
    if g.intentos_reescritura > 0:
        lineas.append(f"✏️ Reescrituras: {g.intentos_reescritura}")
    return "\n".join(lineas) + "\n" if lineas else ""


def _det_visual(estado: EstadoProyecto) -> str:
    v = estado.visual
    lineas = []
    partes = []
    if v.imagenes:
        partes.append(f"{len(v.imagenes)} imágenes")
    if v.clips_video:
        partes.append(f"{len(v.clips_video)} clips")
    if partes:
        lineas.append(f"🖼 {' · '.join(partes)}")
    if v.estilo_aplicado:
        lineas.append(f"🎨 Estilo: {_e(v.estilo_aplicado)}")
    return "\n".join(lineas) + "\n" if lineas else ""


def _det_audio(estado: EstadoProyecto) -> str:
    a = estado.audio
    lineas = []
    if a.voz_path:
        lineas.append("🎙 Locución: generada")
    if a.musica_path:
        fuente = f" ({a.musica_fuente})" if a.musica_fuente else ""
        lineas.append(f"🎵 Música: generada{fuente}")
    if a.subtitulos_path:
        lineas.append("📝 Subtítulos: generados")
    return "\n".join(lineas) + "\n" if lineas else ""


def _det_cierre(estado: EstadoProyecto) -> str:
    lineas = []
    if estado.video_final_path:
        lineas.append("🎬 Video: renderizado")
    n_tags = len(estado.metadata.tags)
    if n_tags:
        lineas.append(f"🔍 SEO: {n_tags} tags")
    if estado.compliance.nivel_riesgo:
        ok = "✅" if estado.compliance.aprobado else "⚠️"
        lineas.append(f"🛡 Compliance: {estado.compliance.nivel_riesgo} {ok}")
    if estado.publicado and estado.youtube_video_id:
        lineas.append(f"📤 Publicado: youtu.be/{estado.youtube_video_id}")
    return "\n".join(lineas) + "\n" if lineas else ""


# ── Resumen final ───────────────────────────────────────────────


def _resumen_final(
    proyecto_id: str,
    estado: EstadoProyecto,
    duracion_total: float,
    tiempos_fases: dict[str, float],
) -> str:
    titulo = _e(estado.estrategia.titulo_ganador or "Sin título")
    n_escenas = len(estado.guion.escenas)
    n_imgs = len(estado.visual.imagenes)
    n_clips = len(estado.visual.clips_video)
    n_tags = len(estado.metadata.tags)

    msg = (
        f"{_pc()}🎬 <b>PIPELINE COMPLETADO</b>\n"
        f"📁 <code>{_e(proyecto_id)}</code> · 📺 {_e(estado.canal)}\n"
        f"⏱ Tiempo total: <b>{_dur(duracion_total)}</b>\n\n"
        f"<b>📊 Resumen:</b>\n"
    )

    msg += f'  📝 Título: "{titulo}"'
    if estado.estrategia.titulo_score is not None:
        msg += f" ({estado.estrategia.titulo_score})"
    msg += "\n"

    msg += f"  🎬 Guión: {n_escenas} escenas"
    if estado.guion.score is not None:
        msg += f" ({estado.guion.score}/100)"
    msg += "\n"

    v_parts = []
    if n_imgs:
        v_parts.append(f"{n_imgs} imgs")
    if n_clips:
        v_parts.append(f"{n_clips} clips")
    msg += f"  🖼 Visuales: {' + '.join(v_parts) if v_parts else 'N/A'}\n"

    a_parts = []
    if estado.audio.voz_path:
        a_parts.append("locución")
    if estado.audio.musica_path:
        a_parts.append("música")
    if estado.audio.subtitulos_path:
        a_parts.append("subs")
    msg += f"  🎙 Audio: {' + '.join(a_parts) if a_parts else 'N/A'}\n"

    if estado.video_final_path:
        msg += "  🎬 Video: renderizado\n"
    if n_tags:
        msg += f"  🔍 SEO: {n_tags} tags\n"
    if estado.compliance.nivel_riesgo:
        ok = "✅" if estado.compliance.aprobado else "⚠️"
        msg += f"  🛡 Compliance: {estado.compliance.nivel_riesgo} {ok}\n"
    if estado.publicado and estado.youtube_video_id:
        msg += f"  📤 YouTube: youtu.be/{estado.youtube_video_id}\n"

    if tiempos_fases:
        msg += f"\n<b>⏱ Tiempos:</b>\n"
        partes = []
        for fase in _ETAPAS:
            if fase in tiempos_fases:
                partes.append(f"{_NOMBRES[fase]} {_dur(tiempos_fases[fase])}")
        for i in range(0, len(partes), 3):
            msg += "  " + " · ".join(partes[i : i + 3]) + "\n"

    msg += "\n✅✅✅✅✅ Pipeline completo"
    return msg
