"""
Agente 0.6 - Planificador de Contenido
Depto 0 (Inteligencia de Canal)

Genera cronogramas estrategicos de publicacion para periodos de 7-30 dias
usando Claude (Code SDK) para razonamiento estrategico de alto nivel.

Dos modos de operacion:

  Modo "generar":
    Crea un cronograma completo analizando competidores, tendencias,
    brechas, patrones exitosos y keywords de alto rendimiento.
    Cada video tiene fecha, orden estrategico y justificacion con datos.

  Modo "revisar":
    Valida una entrada especifica del cronograma antes de producirla.
    Decide: proceder / ajustar / sustituir segun datos frescos del mercado.
"""

import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

import uvicorn
from fastapi import FastAPI

from shared.base_agent import crear_agente_app, envolver_logica
from shared.channel_manager import ChannelManager
from shared.claude_client import generar_json_claude
from shared.config import REGISTRO_AGENTES
from shared.knowledge_loader import inyectar_knowledge
from shared.logger import get_logger
from shared import telegram_notifier as telegram
from shared.schemas import (
    AgenteRequest,
    AgenteResponse,
    CronogramaContenido,
    EntradaCronograma,
)

AGENTE_ID = "0.6_planificador_contenido"
app: FastAPI = crear_agente_app(
    AGENTE_ID,
    descripcion="Genera cronogramas estrategicos de contenido para YouTube",
)
channels = ChannelManager()
log = get_logger(AGENTE_ID)

DIAS_SEMANA = [
    "Lunes", "Martes", "Miercoles", "Jueves",
    "Viernes", "Sabado", "Domingo",
]

# ── System Prompts ────────────────────────────────────────────

SYSTEM_PROMPT_GENERAR = """Eres un estratega de contenido de YouTube de nivel experto.
Tu especialidad es crear cronogramas de publicacion estrategicos basados en datos reales,
ADAPTADOS a la fase de madurez del canal.

NO generas ideas aleatorias. Cada video que planificas tiene:
1. Una FECHA especifica con justificacion (por que ese dia y no otro)
2. Un ORDEN estrategico (por que este video va antes que el otro)
3. DATOS reales que lo respaldan (competidor X, tendencia Y, brecha Z)

========================================================================
ESTRATEGIAS DE SECUENCIAMIENTO POR FASE DE MADUREZ DEL CANAL
========================================================================

>> FASE LANZAMIENTO (canal nuevo, <30 videos, <1K suscriptores):
   Objetivo: que el algoritmo de YouTube conozca tu canal rapido.

   Semana 1 - TESTEO AGRESIVO:
     60% trending (views rapidas para que el algoritmo te indexe)
     40% evergreen (base de contenido que sigue trayendo trafico)
     Titulos mas agresivos, CTR alto es critico para ganar impresiones
     Videos de 8-12 min (suficientes para watch time, no tan largos que asusten)

   Semana 2 - LECTURA DE SENALES:
     Si algun video destaco → follow-up o tema relacionado inmediato
     Si nada destaco → cambiar angulo, no repetir el mismo enfoque
     50% trending + 30% brechas de contenido + 20% follow-up

   Semana 3 - CONSTRUCCION:
     Mas evergreen para trafico organico sostenido
     Si un tema probo ser exitoso → iniciar mini-serie
     30% trending + 40% evergreen + 30% brechas/follow-up

   Semana 4 - OPTIMIZACION:
     Formula ganadora identificada → replicar con variaciones
     Contenido que maximice watch time (para llegar a monetizacion)
     20% trending + 40% evergreen + 40% formula ganadora

>> FASE CRECIMIENTO (canal con trayectoria, 30+ videos o 1K-10K subs):
   Objetivo: optimizar lo que funciona, llenar huecos estrategicos.

   Los datos reales de performance SON LA GUIA PRINCIPAL, no las tendencias genericas.
   Priorizar patrones exitosos del canal sobre tendencias del nicho.
   Llenar brechas de contenido para posicionamiento a largo plazo.
   Counter-programming: publicar cuando los competidores no lo hacen.
   Iniciar series sobre temas que ya probaron funcionar.
   Mezcla: 30% trending/reaccion + 30% evergreen/brechas + 40% follow-up/series

   Regla clave: si el canal tiene patrones exitosos claros, el cronograma
   debe replicar esos patrones (mismo formato, estilo de titulo, duracion)
   pero con temas nuevos. No reinventar lo que ya funciona.

>> FASE ESCALA (canal establecido, 10K+ subs o ya monetizado):
   Objetivo: maximizar revenue y crecimiento sostenible.

   Watch time > views (retencion es mas importante que clicks)
   Series y contenido recurrente (la audiencia espera consistencia)
   Trending SOLO cuando alinea con la identidad del canal
   Explorar formatos nuevos con 10-15% del calendario (innovacion controlada)
   Contenido mas largo y profundo (la audiencia ya te conoce y confía)
   Mezcla: 20% trending + 35% evergreen/series + 30% core optimizado + 15% experimental

   Regla clave: no perseguir tendencias que no encajan con la marca del canal.
   La consistencia en identidad y calidad es mas valiosa que views puntuales.

========================================================================
REGLAS DE ADAPTACION CONTINUA (aplican a TODAS las fases)
========================================================================

ENTORNO EXTERNO (competidores):
- Si un competidor publico un tema exitoso → tu version mejorada en 48-72h
- Si un competidor dejo de publicar (>2 semanas inactivo) → oportunidad de capturar su audiencia
- Si multiples competidores cubren un tema → diferenciarte con angulo unico, no competir de frente
- Dias con menos publicaciones del nicho → oportunidad de menor competencia

ENTORNO INTERNO (tus propios resultados):
- Video con 2x+ del promedio → programar follow-up o serie en los proximos 3-5 dias
- Video con <50% del promedio → NO programar tema similar, cambiar de angulo
- Si un formato funciona consistentemente → aumentar su proporcion en el plan
- Si un dia de la semana funciona mejor → concentrar los videos importantes ahi
- CTR alto + retencion baja = buen empaque, mejorar el contenido siguiente
- CTR bajo + retencion alta = buen contenido, mejorar titulo/thumbnail

REGLAS DE SECUENCIAMIENTO (aplican a TODAS las fases):
- No poner mas de 2 videos del mismo tipo_contenido consecutivos
- Temas trending van temprano (ventana de oportunidad se cierra)
- Despues de un trending, intercalar evergreen (trending atrae, evergreen retiene)
- Las brechas son oro: nadie las cubre pero la audiencia las busca
- Alternar formatos para mantener variedad (no 3 listicles seguidos)
- El video MAS importante NO va en el primer slot (calibrar con 1-2 videos primero)
- Variar patrones de titulo exitosos para distintos temas (no repetir titulo identico)

REGLAS DE TIMING COMPETITIVO:
- Consulta el MAPA DE PRESION para elegir las fechas de cada video
- Los videos de MAYOR prioridad van en dias con MENOR presion competitiva
- Usa las VENTANAS DE PRE-EMISION: si un competidor publica los viernes,
  programa tu video similar para el jueves
- Si hay competidores INACTIVOS, prioriza temas que cubran su nicho desatendido
- Trending content va en dias de baja presion para maximizar impresiones
  sin competir con otros creators publicando trending el mismo dia
- Evergreen puede ir en dias de alta presion (no depende de timing)
- En razon_fecha, menciona ESPECIFICAMENTE el dato de timing que justifica
  la eleccion (ej: "presion 2/10, CompA publica trending el viernes, ganar ventana")

REGLAS DE CALIDAD:
- Titulos deben seguir patrones que YA funcionan en el canal cuando los haya
- potencial_viral es un score 1.0-10.0 basado en datos reales, no optimismo
- Keywords deben venir del keyword tracker cuando sea posible
- No inventar datos de competidores que no se proporcionaron
- duracion_sugerida_min realista para el formato (listicle: 8-12, tutorial: 10-20, storytime: 12-18)

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "estrategia_general": "logica de secuenciamiento del plan adaptada a la fase del canal (2-3 frases)",
  "cadencia_recomendada": "ej: 4 videos/semana, publicar Lun/Mie/Vie/Dom a las 14:00",
  "distribucion_tipos": {
    "trending": 30,
    "brecha": 20,
    "evergreen": 25,
    "follow_up": 15,
    "serie": 10,
    "viral_reaccion": 0
  },
  "entradas": [
    {
      "dia": 1,
      "fecha_programada": "2026-07-01",
      "titulo_sugerido": "titulo optimizado y clickeable",
      "tema": "descripcion breve del tema (1-2 frases)",
      "angulo": "el enfoque especifico que diferencia este video de los demas",
      "tipo_contenido": "trending|brecha|evergreen|follow_up|serie|viral_reaccion",
      "formato": "tutorial|listicle|storytime|comparacion|caso_estudio|reaccion|explicacion",
      "duracion_sugerida_min": 10,
      "prioridad": "alta|media|baja",
      "potencial_viral": 7.5,
      "razon_fecha": "por que este dia (basado en datos de competencia, tendencias o algoritmo)",
      "razon_tema": "por que este tema ahora (basado en brechas, tendencias, patrones o fase del canal)",
      "keywords_recomendadas": ["keyword1", "keyword2", "keyword3"],
      "datos_soporte": {
        "fuente": "dato concreto que respalda esta decision",
        "competidor_referencia": "competidor o tendencia que inspira esto"
      }
    }
  ]
}

"distribucion_tipos" muestra el % planeado de cada tipo en el cronograma.
Los porcentajes deben sumar 100 y reflejar la estrategia de la fase del canal.

Genera EXACTAMENTE el numero de entradas solicitado.
Ordena cronologicamente por fecha_programada.
Usa SOLO fechas de la lista de fechas disponibles proporcionada.
No repitas fechas entre entradas."""


SYSTEM_PROMPT_REVISAR = """Eres un validador estrategico de contenido para YouTube.
Tu trabajo es decidir si un video planificado en un cronograma sigue siendo la
mejor opcion para producir HOY, o si necesita ajustes basados en lo que ha
cambiado desde que se planifico.

Recibes datos pre-analizados en estas categorias:
1. La entrada original del cronograma con sus razones
2. ALERTA DE SOLAPAMIENTO: si algun competidor ya cubrio un tema similar
3. SENAL DE PERFORMANCE: si el ultimo video propio tuvo resultados excepcionales o pobres
4. TENDENCIAS FRESCAS: busqueda web en tiempo real del nicho
5. FRESCURA DE DATOS: que tan actualizados estan los datos de inteligencia
6. ENTRADAS FUTURAS: que viene despues en el cronograma (para evaluar impacto en cascada)

========================================================================
CRITERIOS DE DECISION (en orden de peso)
========================================================================

1. EVENTO TRENDING URGENTE (peso: ALTO)
   Si hay un evento o tendencia NUEVA que no existia cuando se creo el plan,
   y tiene ventana de oportunidad de <48h, considerar SUSTITUIR.
   Pero SOLO si el trending alinea con el nicho del canal.

2. PERFORMANCE EXCEPCIONAL DEL VIDEO ANTERIOR (peso: ALTO)
   Si el ultimo video tuvo 2x+ del promedio del canal → considerar SUSTITUIR
   para hacer un follow-up inmediato y capitalizar el momentum del algoritmo.
   Si tuvo <50% del promedio → considerar AJUSTAR el angulo del video planeado
   para diferenciarse del patron que fallo.

3. SOLAPAMIENTO CON COMPETIDORES (peso: MEDIO)
   Si un competidor publico algo MUY similar en los ultimos 3 dias:
   - NO es razon para SUSTITUIR (tu audiencia no es la misma)
   - SI es razon para AJUSTAR: cambiar angulo, diferenciarte, o hacer
     una version que responda/mejore lo que el competidor publico
   Si el competidor lo publico hace >7 dias: no es relevante, PROCEDER.

4. CAMBIO EN TENDENCIAS (peso: MEDIO)
   Si las tendencias del nicho cambiaron significativamente desde la
   generacion del cronograma, puede justificar un AJUSTE de angulo
   para incorporar la tendencia nueva al tema planificado.

5. IMPACTO EN SECUENCIA (peso: BAJO pero importante)
   Si sustituyes esta entrada, evalua como afecta las siguientes.
   No sustituyas por un tema que ya esta planeado para una entrada futura.
   Si el tema sustituido sigue siendo valido, sugiere reubicar en
   "fecha_reubicacion" para un slot posterior.

========================================================================
REGLAS DE DECISION
========================================================================

PROCEDER cuando:
- No hay cambios significativos desde la planificacion
- Los datos de soporte originales siguen siendo validos
- No hay trending urgente ni performance excepcional que cambie prioridades
- Los competidores no han cubierto el tema de forma que invalide tu angulo

AJUSTAR cuando:
- El tema sigue siendo correcto pero el angulo necesita diferenciacion
- Un competidor publico algo similar (diferenciarte, no copiar)
- Surgio un dato o tendencia nueva que enriquece el tema sin cambiarlo
- El performance del video anterior sugiere un tono o formato diferente
- Las keywords originales pueden mejorarse con datos frescos

SUSTITUIR cuando (CONSERVADOR — necesitas evidencia fuerte):
- Hay un evento trending urgente con ventana <48h que alinea con el nicho
- El ultimo video tuvo performance excepcional y un follow-up inmediato
  capturaria momentum del algoritmo (esto es mas valioso que el plan original)
- El tema planificado ya fue cubierto exhaustivamente por 2+ competidores
  en los ultimos 3 dias Y no hay angulo diferenciador viable

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "decision": "proceder|ajustar|sustituir",
  "confianza": 8.5,
  "score_vigencia": 7.0,
  "razon": "explicacion concisa con datos especificos (2-3 frases)",
  "factores_evaluados": {
    "solapamiento_competidores": "ninguno|bajo|medio|alto",
    "senal_performance": "sin_datos|excepcional|normal|pobre",
    "trending_urgente": "no|si_bajo|si_alto",
    "frescura_datos": "frescos|aceptables|desactualizados",
    "impacto_secuencia": "ninguno|bajo|medio"
  },
  "cambios_detectados": ["cambio relevante 1", "cambio 2"],
  "entrada_actualizada": {
    "titulo_sugerido": "titulo original o ajustado",
    "tema": "tema original o ajustado",
    "angulo": "angulo original o ajustado",
    "formato": "formato original o ajustado",
    "keywords_recomendadas": ["kw1", "kw2"],
    "duracion_sugerida_min": 10,
    "razon_ajuste": "null si proceder, explicacion si ajustar/sustituir"
  },
  "alternativa": null,
  "reubicar_original": false,
  "fecha_reubicacion_sugerida": null
}

"score_vigencia" es de 1.0 a 10.0:
  9-10: entrada perfectamente vigente, datos de soporte intactos
  7-8: vigente con ajustes menores posibles
  5-6: vigencia media, ajustes recomendados
  3-4: vigencia baja, sustitucion recomendada
  1-2: entrada obsoleta, sustitucion necesaria

Si decision es SUSTITUIR, "alternativa" debe contener:
{
  "titulo_sugerido": "titulo del video sustituto",
  "tema": "tema alternativo",
  "angulo": "nuevo angulo",
  "tipo_contenido": "trending|brecha|evergreen|follow_up|serie|viral_reaccion",
  "formato": "tutorial|listicle|storytime|comparacion|caso_estudio|reaccion|explicacion",
  "duracion_sugerida_min": 10,
  "razon": "por que este video es mejor que el planificado (con datos)"
}

Si decision es SUSTITUIR y el tema original sigue siendo valido (solo pierde
por timing), pon "reubicar_original": true y sugiere una fecha futura en
"fecha_reubicacion_sugerida" (debe ser un slot sin video asignado)."""


# ── Clasificacion de madurez del canal ────────────────────────

def _clasificar_madurez_canal(estado) -> dict:
    subs = estado.suscriptores or 0
    videos = estado.video_count or 0
    videos_analizados = estado.promedios_canal.total_videos_analizados
    n_exitosos = len(estado.patrones_exitosos)
    n_evitar = len(estado.patrones_a_evitar)
    dias_creado = None
    if estado.creado_youtube:
        dias_creado = (datetime.utcnow() - estado.creado_youtube).days

    if subs >= 10_000 or (subs >= 1_000 and videos >= 50):
        fase = "escala"
        descripcion = "Canal establecido o monetizado"
        guia = (
            "Priorizar watch time y retencion sobre views puntuales. "
            "Series y contenido recurrente. Trending solo si alinea con la marca. "
            "Experimentar con 10-15% del calendario. "
            "Mezcla: 20% trending + 35% evergreen/series + 30% core + 15% experimental."
        )
    elif videos >= 30 or subs >= 1_000:
        fase = "crecimiento"
        descripcion = "Canal con trayectoria, en fase de crecimiento"
        guia = (
            "Los datos de performance son la GUIA PRINCIPAL. "
            "Replicar patrones exitosos con temas nuevos. "
            "Counter-programming contra competidores. Iniciar series probadas. "
            "Mezcla: 30% trending + 30% evergreen/brechas + 40% follow-up/series."
        )
    else:
        fase = "lanzamiento"
        descripcion = "Canal nuevo o en fase temprana"
        guia = (
            "El algoritmo necesita conocer el canal. Testeo agresivo semana 1. "
            "Redoblar lo que funcione en semana 2. Construir base evergreen semana 3. "
            "Optimizar la formula ganadora semana 4. "
            "Mezcla inicial: 60% trending + 40% evergreen, ajustar segun resultados."
        )

    tiene_performance = videos_analizados >= 3
    tiene_patrones = n_exitosos >= 2

    nivel_datos = "completo"
    if not tiene_performance and not tiene_patrones:
        nivel_datos = "sin_datos"
    elif tiene_performance and not tiene_patrones:
        nivel_datos = "basico"

    return {
        "fase": fase,
        "descripcion": descripcion,
        "guia_estrategica": guia,
        "suscriptores": subs,
        "videos_publicados": videos,
        "dias_creado": dias_creado,
        "videos_con_performance": videos_analizados,
        "patrones_exitosos": n_exitosos,
        "patrones_a_evitar": n_evitar,
        "tiene_datos_performance": tiene_performance,
        "tiene_patrones": tiene_patrones,
        "nivel_datos": nivel_datos,
    }


# ── Analisis de timing de competidores ────────────────────────

def _analizar_timing_competidores(competidores) -> dict:
    dia_stats = {
        dia: {"publicaciones": 0, "competidores": set(), "vistas_total": 0}
        for dia in DIAS_SEMANA
    }
    detalle_competidores = []
    inactivos = []

    for comp in competidores:
        fechas_videos = [
            (v.publicado_en, v)
            for v in comp.videos_recientes
            if v.publicado_en
        ]
        if len(fechas_videos) < 2:
            continue

        fechas_videos.sort(key=lambda x: x[0])

        dias_comp = Counter()
        titulos_por_dia: dict[str, list[str]] = {}
        for fecha, v in fechas_videos:
            dia = DIAS_SEMANA[fecha.weekday()]
            dias_comp[dia] += 1
            dia_stats[dia]["publicaciones"] += 1
            dia_stats[dia]["competidores"].add(comp.nombre)
            dia_stats[dia]["vistas_total"] += v.vistas
            titulos_por_dia.setdefault(dia, []).append(v.titulo)

        fechas_solo = [f for f, _ in fechas_videos]
        intervalos = [
            (fechas_solo[i + 1] - fechas_solo[i]).days
            for i in range(len(fechas_solo) - 1)
            if (fechas_solo[i + 1] - fechas_solo[i]).days > 0
        ]
        freq_dias = round(sum(intervalos) / len(intervalos), 1) if intervalos else 0
        dias_fav = [d for d, _ in dias_comp.most_common(3)]
        dias_desde_ultimo = (datetime.utcnow() - fechas_solo[-1]).days

        if freq_dias > 0 and dias_desde_ultimo > freq_dias * 2:
            inactivos.append({
                "nombre": comp.nombre,
                "suscriptores": comp.suscriptores,
                "frecuencia_normal_dias": freq_dias,
                "dias_inactivo": dias_desde_ultimo,
                "factor_inactividad": round(dias_desde_ultimo / freq_dias, 1),
            })

        detalle_competidores.append({
            "nombre": comp.nombre,
            "suscriptores": comp.suscriptores,
            "frecuencia_cada_n_dias": freq_dias,
            "dias_favoritos": dias_fav,
            "total_videos_analizados": len(fechas_videos),
            "dias_desde_ultimo_video": dias_desde_ultimo,
            "contenido_por_dia": {
                dia: titulos[:3] for dia, titulos in titulos_por_dia.items()
            },
        })

    # ── Mapa de presion competitiva por dia ──
    max_pubs = max(
        (dia_stats[d]["publicaciones"] for d in DIAS_SEMANA), default=1,
    ) or 1

    mapa_presion = {}
    for dia in DIAS_SEMANA:
        stats = dia_stats[dia]
        n_comp = len(stats["competidores"])
        presion = min(round((stats["publicaciones"] / max_pubs) * 10), 10)
        vistas_prom = (
            round(stats["vistas_total"] / stats["publicaciones"])
            if stats["publicaciones"] > 0 else 0
        )

        if presion <= 2:
            recomendacion = "EXCELENTE — muy baja competencia"
        elif presion <= 4:
            recomendacion = "BUENO — competencia manejable"
        elif presion <= 6:
            recomendacion = "MEDIO — considerar diferenciacion de angulo"
        elif presion <= 8:
            recomendacion = "ALTO — solo contenido muy diferenciado"
        else:
            recomendacion = "MUY ALTO — evitar si hay alternativa"

        mapa_presion[dia] = {
            "presion": presion,
            "publicaciones_total": stats["publicaciones"],
            "competidores_activos": n_comp,
            "competidores_nombres": sorted(stats["competidores"]),
            "vistas_promedio": vistas_prom,
            "recomendacion": recomendacion,
        }

    # ── Ventanas de pre-emision ──
    ventanas = []
    for det in detalle_competidores:
        for dia_fav in det["dias_favoritos"][:2]:
            idx = DIAS_SEMANA.index(dia_fav)
            dia_antes = DIAS_SEMANA[(idx - 1) % 7]
            presion_antes = mapa_presion[dia_antes]["presion"]

            if presion_antes <= 5:
                ventanas.append({
                    "competidor": det["nombre"],
                    "suscriptores": det["suscriptores"],
                    "dia_competidor": dia_fav,
                    "dia_preemision": dia_antes,
                    "presion_dia_preemision": presion_antes,
                })

    # ── Slots optimos (ordenados de mejor a peor) ──
    slots_ranking = sorted(
        mapa_presion.items(),
        key=lambda x: (x[1]["presion"], -x[1]["vistas_promedio"]),
    )
    slots_optimos = [
        {
            "dia": dia,
            "presion": data["presion"],
            "competidores": data["competidores_activos"],
            "recomendacion": data["recomendacion"],
        }
        for dia, data in slots_ranking
    ]

    return {
        "mapa_presion": mapa_presion,
        "ventanas_preemision": ventanas,
        "competidores_inactivos": inactivos,
        "detalle_competidores": detalle_competidores,
        "slots_optimos": slots_optimos,
    }


def _formatear_timing_para_prompt(timing: dict) -> str:
    """Formatea el analisis de timing en texto legible para el prompt de Claude."""
    lineas = []

    # Mapa de presion
    mapa = timing.get("mapa_presion", {})
    if mapa:
        lineas.append("MAPA DE PRESION COMPETITIVA POR DIA:")
        for dia in DIAS_SEMANA:
            if dia not in mapa:
                continue
            d = mapa[dia]
            barra = "█" * d["presion"] + "░" * (10 - d["presion"])
            comps = ", ".join(d["competidores_nombres"]) if d["competidores_nombres"] else "ninguno"
            lineas.append(
                f"  {dia:10s} {barra} {d['presion']:2d}/10 | "
                f"{d['competidores_activos']} comp ({comps}) | "
                f"{d['recomendacion']}"
            )

    # Ventanas de pre-emision
    ventanas = timing.get("ventanas_preemision", [])
    if ventanas:
        lineas.append("")
        lineas.append("VENTANAS DE PRE-EMISION (publicar ANTES que el competidor):")
        for v in ventanas:
            lineas.append(
                f"  → {v['competidor']} ({v.get('suscriptores', '?')} subs) "
                f"publica en {v['dia_competidor']} "
                f"→ publicar en {v['dia_preemision']} para ganar la ventana "
                f"(presion {v['dia_preemision']}: {v['presion_dia_preemision']}/10)"
            )

    # Competidores inactivos
    inactivos = timing.get("competidores_inactivos", [])
    if inactivos:
        lineas.append("")
        lineas.append("COMPETIDORES INACTIVOS (OPORTUNIDAD DE CAPTURA):")
        for ci in inactivos:
            lineas.append(
                f"  → {ci['nombre']} ({ci.get('suscriptores', '?')} subs): "
                f"INACTIVO {ci['dias_inactivo']} dias "
                f"(normal: cada {ci['frecuencia_normal_dias']} dias, "
                f"{ci['factor_inactividad']}x su frecuencia normal). "
                f"Su audiencia esta desatendida."
            )

    # Slots optimos
    slots = timing.get("slots_optimos", [])
    if slots:
        lineas.append("")
        lineas.append("RANKING DE SLOTS OPTIMOS (de mejor a peor):")
        for i, s in enumerate(slots):
            marcador = "★" if i < 3 else " "
            lineas.append(
                f"  {marcador} {i+1}. {s['dia']} (presion {s['presion']}/10, "
                f"{s['competidores']} competidores) — {s['recomendacion']}"
            )
        peores = [s for s in slots if s["presion"] >= 7]
        if peores:
            evitar = ", ".join(f"{s['dia']} ({s['presion']}/10)" for s in peores)
            lineas.append(f"  EVITAR: {evitar}")

    # Detalle por competidor
    detalle = timing.get("detalle_competidores", [])
    if detalle:
        lineas.append("")
        lineas.append("DETALLE POR COMPETIDOR:")
        for cd in detalle:
            lineas.append(
                f"  - {cd['nombre']} ({cd.get('suscriptores', '?')} subs): "
                f"publica cada {cd['frecuencia_cada_n_dias']} dias, "
                f"favorece {', '.join(cd['dias_favoritos'])}, "
                f"ultimo video hace {cd['dias_desde_ultimo_video']} dias"
            )
            contenido = cd.get("contenido_por_dia", {})
            if contenido:
                for dia_c, titulos in list(contenido.items())[:3]:
                    lineas.append(
                        f"      {dia_c}: {', '.join(f'«{t}»' for t in titulos[:2])}"
                    )

    return "\n".join(lineas) if lineas else "(sin datos de timing de competidores)"


def _obtener_top_keywords_texto(limite: int = 15) -> str:
    try:
        from shared.keyword_tracker import top_keywords

        keywords = top_keywords(limit=limite, min_usos=1)
        if not keywords:
            return "(sin datos de keywords aun)"
        lineas = []
        for kw in keywords:
            partes = [f"'{kw['keyword']}'"]
            partes.append(f"{kw['vistas_promedio']:.0f} vistas prom")
            if kw.get("ctr_promedio"):
                partes.append(f"CTR {kw['ctr_promedio']}%")
            if kw.get("engagement_promedio"):
                partes.append(f"eng {kw['engagement_promedio']}%")
            partes.append(f"{kw['usos']} uso(s)")
            lineas.append("- " + " | ".join(partes))
        return "\n".join(lineas)
    except Exception:
        return "(keyword tracker no disponible)"


def _extraer_feedback_cronograma_anterior(estado) -> str:
    """Extrae aprendizajes del cronograma anterior: plan vs ejecucion vs resultados."""
    fuentes = []

    if estado.cronograma_activo:
        fuentes.append(estado.cronograma_activo)

    for hist in (estado.cronogramas_historial or [])[-2:]:
        try:
            fuentes.append(CronogramaContenido(**hist))
        except Exception:
            pass

    aprendizajes = []
    for cron in fuentes:
        for e in cron.entradas:
            if e.status != "publicado":
                continue

            feedback_perf = None
            for aj in e.ajustes_historial:
                if isinstance(aj.get("decision"), str) and aj["decision"].startswith("feedback_performance"):
                    feedback_perf = aj.get("performance", {})

            if not feedback_perf:
                continue

            titulo_plan = feedback_perf.get("titulo_planeado", e.titulo_sugerido)
            titulo_real = feedback_perf.get("titulo_ejecutado", e.titulo_final or "?")
            desviado = feedback_perf.get("titulo_desviado", False)
            ratio = feedback_perf.get("ratio_vs_promedio", "?")
            score = feedback_perf.get("score", "?")
            tipo = e.tipo_contenido
            formato = e.formato

            resultado = "EXITOSO" if isinstance(ratio, (int, float)) and ratio >= 130 else (
                "POBRE" if isinstance(ratio, (int, float)) and ratio < 50 else "NORMAL"
            )

            linea = (
                f"- Plan: \"{titulo_plan}\" [{tipo}/{formato}] → "
                f"Ejecutado: \"{titulo_real}\""
            )
            if desviado:
                linea += " (titulo MODIFICADO vs plan)"
            linea += (
                f" → Resultado: {resultado} "
                f"({ratio}% vs prom, score {score})"
            )
            aprendizajes.append(linea)

    if not aprendizajes:
        return "(sin feedback de cronogramas anteriores)"

    return "\n".join(aprendizajes[-10:])


def _generar_fechas_disponibles(fecha_inicio: datetime, periodo_dias: int) -> str:
    lineas = []
    for i in range(periodo_dias):
        fecha = fecha_inicio + timedelta(days=i)
        dia_sem = DIAS_SEMANA[fecha.weekday()]
        lineas.append(f"  {fecha.strftime('%Y-%m-%d')} ({dia_sem})")
    return "\n".join(lineas)


def _resumen_entradas_completadas(cronograma: CronogramaContenido) -> str:
    completadas = [
        e for e in cronograma.entradas
        if e.status in ("publicado", "en_produccion", "aprobado")
    ]
    if not completadas:
        return "(ninguno aun)"
    lineas = []
    for e in completadas:
        titulo = e.titulo_final or e.titulo_sugerido
        lineas.append(
            f"- Dia {e.dia} ({e.fecha_programada}): \"{titulo}\" "
            f"[{e.status}] tipo={e.tipo_contenido}"
        )
    return "\n".join(lineas)


# ── Modo GENERAR ──────────────────────────────────────────────

def _generar_cronograma(
    canal_id: str,
    periodo_dias: int,
    frecuencia_semanal: int,
    fecha_inicio_str: str | None,
) -> dict:
    estado = channels.leer(canal_id)
    perfil = estado.perfil

    if fecha_inicio_str:
        fecha_inicio = datetime.fromisoformat(fecha_inicio_str)
    else:
        fecha_inicio = (datetime.utcnow() + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )

    fecha_fin = fecha_inicio + timedelta(days=periodo_dias - 1)
    total_videos = max(round((periodo_dias / 7) * frecuencia_semanal), 1)

    # ── 0. Clasificar madurez del canal ──
    madurez = _clasificar_madurez_canal(estado)

    # ── 1. Timing de competidores (analisis profundo) ──
    timing = _analizar_timing_competidores(estado.competidores)
    timing_texto = _formatear_timing_para_prompt(timing)

    # ── 2. Top videos de competidores ──
    comp_top = []
    for comp in estado.competidores[:5]:
        titulos = [
            f"\"{v.titulo}\" ({v.vistas:,} vistas)"
            for v in comp.top_videos[:5]
        ]
        recientes = [f"\"{v.titulo}\"" for v in comp.videos_recientes[:5]]
        comp_top.append(
            f"- {comp.nombre} ({comp.suscriptores or '?'} subs):\n"
            f"    Top: {', '.join(titulos) if titulos else 'N/A'}\n"
            f"    Recientes: {', '.join(recientes) if recientes else 'N/A'}"
        )

    # ── 3. Patrones exitosos del canal ──
    exitosos = []
    for p in estado.patrones_exitosos[-10:]:
        exitosos.append(
            f"- \"{p.get('titulo', '?')}\" -> {p.get('vistas', 0):,} vistas, "
            f"CTR {p.get('ctr', '?')}%, "
            f"ratio {p.get('ratio_vs_promedio', '?')}% vs promedio"
        )

    evitar = []
    for p in estado.patrones_a_evitar[-10:]:
        evitar.append(
            f"- \"{p.get('titulo', '?')}\" -> {p.get('vistas', 0):,} vistas, "
            f"ratio {p.get('ratio_vs_promedio', '?')}% vs promedio"
        )

    # ── 4. Ideas previas (no repetir) ──
    ideas_previas = [
        i.get("titulo_sugerido", "?") for i in estado.ideas_historial[-30:]
    ]

    temas_cronograma_previo = []
    if estado.cronograma_activo and estado.cronograma_activo.entradas:
        temas_cronograma_previo = [
            e.titulo_sugerido for e in estado.cronograma_activo.entradas
        ]

    # ── 5. Keywords, fechas y feedback del cronograma anterior ──
    keywords_texto = _obtener_top_keywords_texto()
    fechas_texto = _generar_fechas_disponibles(fecha_inicio, periodo_dias)
    feedback_texto = _extraer_feedback_cronograma_anterior(estado)

    # ── 6. Promedios del canal ──
    prom = estado.promedios_canal
    promedios_texto = "(sin datos suficientes)"
    if prom.total_videos_analizados >= 3:
        promedios_texto = (
            f"Vistas prom: {prom.vistas_promedio:,.0f} | "
            f"CTR prom: {prom.ctr_promedio or '?'}% | "
            f"Retencion prom: {prom.retencion_promedio or '?'}% | "
            f"Engagement prom: {prom.engagement_rate_promedio or '?'}% | "
            f"Videos analizados: {prom.total_videos_analizados}"
        )

    # ── Construir prompt ──
    madurez_texto = (
        f"Fase: {madurez['fase'].upper()} — {madurez['descripcion']}\n"
        f"Suscriptores: {madurez['suscriptores']:,} | "
        f"Videos publicados: {madurez['videos_publicados']} | "
        f"Antiguedad: {madurez['dias_creado'] or '?'} dias\n"
        f"Datos de performance: {'SI' if madurez['tiene_datos_performance'] else 'NO'} "
        f"({madurez['videos_con_performance']} videos analizados) | "
        f"Patrones exitosos: {madurez['patrones_exitosos']} | "
        f"Patrones a evitar: {madurez['patrones_a_evitar']}\n"
        f"Nivel de datos disponible: {madurez['nivel_datos']}\n"
        f"GUIA ESTRATEGICA PARA ESTA FASE: {madurez['guia_estrategica']}"
    )

    user_prompt = f"""CANAL: {estado.nombre}
Nicho: {perfil.nicho_principal or 'sin determinar'}
Subnicho: {perfil.subnicho_principal or 'sin determinar'}
Tono: {perfil.tono or 'sin determinar'}
Audiencia: {perfil.audiencia_objetivo or 'sin determinar'}
Formatos exitosos: {', '.join(perfil.formatos_exitosos) if perfil.formatos_exitosos else 'N/A'}
Frecuencia actual: {perfil.frecuencia_publicacion or 'N/A'}
Patrones de titulo exitosos: {', '.join(perfil.patrones_titulo_exitosos) if perfil.patrones_titulo_exitosos else 'N/A'}

=== FASE DE MADUREZ DEL CANAL (CRITICO — adapta tu estrategia a esta fase) ===
{madurez_texto}
===============================================================================

METRICAS PROMEDIO DEL CANAL:
{promedios_texto}

=== ANALISIS DE TIMING DE COMPETIDORES (DIFERENCIAL COMPETITIVO) ===
{timing_texto}
===================================================================

USA ESTE ANALISIS PARA:
- Programar videos importantes en dias con baja presion competitiva
- Aprovechar ventanas de pre-emision (publicar ANTES que el competidor)
- Capitalizar competidores inactivos publicando en sus nichos desatendidos
- EVITAR dias con presion 7+ a menos que el contenido sea muy diferenciado

COMPETIDORES Y SUS VIDEOS:
{chr(10).join(comp_top) if comp_top else '(sin competidores)'}

TENDENCIAS ACTUALES DEL NICHO:
{chr(10).join(f'- {t}' for t in estado.tendencias_nicho) if estado.tendencias_nicho else '(sin tendencias detectadas)'}

BRECHAS DE CONTENIDO (temas que nadie cubre pero la audiencia busca):
{chr(10).join(f'- {b}' for b in estado.brechas_contenido) if estado.brechas_contenido else '(sin brechas detectadas)'}

PATRONES EXITOSOS DEL CANAL (REPLICAR estos patrones):
{chr(10).join(exitosos) if exitosos else '(sin datos de performance aun)'}

PATRONES A EVITAR (bajo rendimiento):
{chr(10).join(evitar) if evitar else '(sin datos aun)'}

TOP KEYWORDS POR RENDIMIENTO HISTORICO:
{keywords_texto}

IDEAS YA GENERADAS ANTERIORMENTE (NO REPETIR):
{chr(10).join(f'- {t}' for t in ideas_previas) if ideas_previas else '(ninguna)'}

TEMAS DE CRONOGRAMA ANTERIOR (NO REPETIR):
{chr(10).join(f'- {t}' for t in temas_cronograma_previo) if temas_cronograma_previo else '(ninguno)'}

=== FEEDBACK DEL CRONOGRAMA ANTERIOR (plan vs ejecucion vs resultado) ===
{feedback_texto}
Usa estos datos para aprender: que tipos/formatos/temas funcionaron y cuales no.
Si un tipo tuvo resultado EXITOSO, planifica mas de ese tipo.
Si tuvo resultado POBRE, evita temas/formatos similares.
Si el titulo se MODIFICO vs el plan y funciono mejor, el plan puede ser mas agresivo.
=====================================================================

FECHAS DISPONIBLES PARA EL PERIODO:
{fechas_texto}

PEDIDO:
Genera un cronograma de exactamente {total_videos} videos para los proximos {periodo_dias} dias.
Frecuencia deseada: {frecuencia_semanal} videos por semana.
Fecha inicio: {fecha_inicio.strftime('%Y-%m-%d')} ({DIAS_SEMANA[fecha_inicio.weekday()]})
Fecha fin: {fecha_fin.strftime('%Y-%m-%d')} ({DIAS_SEMANA[fecha_fin.weekday()]})

Distribuye los {total_videos} videos estrategicamente entre las fechas disponibles.
Cada video debe usar una fecha de la lista anterior. No repitas fechas entre entradas.
Ordena las entradas cronologicamente.

IMPORTANTE: Adapta la distribucion de tipos de contenido y la estrategia de
secuenciamiento a la FASE DE MADUREZ del canal ({madurez['fase'].upper()}).
Sigue la guia estrategica especifica para esta fase.
Si el canal tiene datos de performance, usalos como guia principal.
Si no tiene datos, prioriza testeo y diversidad para obtenerlos rapido."""

    user_prompt = inyectar_knowledge(user_prompt, "depto_0_inteligencia")

    log.info(
        "generando cronograma | canal=%s | fase=%s | periodo=%dd | freq=%d/sem | videos=%d",
        canal_id, madurez["fase"], periodo_dias, frecuencia_semanal, total_videos,
    )

    resultado = generar_json_claude(SYSTEM_PROMPT_GENERAR, user_prompt)

    # ── Parsear entradas ──
    entradas_raw = resultado.get("entradas", [])
    entradas = []
    for i, e in enumerate(entradas_raw):
        entradas.append(EntradaCronograma(
            dia=e.get("dia", i + 1),
            fecha_programada=e.get("fecha_programada", ""),
            titulo_sugerido=e.get("titulo_sugerido", ""),
            tema=e.get("tema", ""),
            angulo=e.get("angulo", ""),
            tipo_contenido=e.get("tipo_contenido", "evergreen"),
            formato=e.get("formato", "explicacion"),
            duracion_sugerida_min=e.get("duracion_sugerida_min", 10),
            prioridad=e.get("prioridad", "media"),
            potencial_viral=e.get("potencial_viral", 5.0),
            razon_fecha=e.get("razon_fecha", ""),
            razon_tema=e.get("razon_tema", ""),
            keywords_recomendadas=e.get("keywords_recomendadas", []),
            datos_soporte=e.get("datos_soporte", {}),
        ))

    # ── Construir cronograma ──
    cronograma_id = (
        f"cron_{canal_id[:8]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    )

    cronograma = CronogramaContenido(
        cronograma_id=cronograma_id,
        canal_id=canal_id,
        periodo_dias=periodo_dias,
        frecuencia_semanal=frecuencia_semanal,
        fecha_inicio=fecha_inicio.strftime("%Y-%m-%d"),
        fecha_fin=fecha_fin.strftime("%Y-%m-%d"),
        generado_en=datetime.utcnow(),
        entradas=entradas,
        cadencia_competidores=timing,
        estrategia_secuencia=resultado.get("estrategia_general", ""),
        madurez_canal=madurez["fase"],
        total_videos=len(entradas),
    )

    # ── Archivar cronograma anterior si existe ──
    cronogramas_hist = list(estado.cronogramas_historial or [])
    if estado.cronograma_activo:
        old_data = json.loads(estado.cronograma_activo.model_dump_json())
        old_data["status"] = "reemplazado"
        cronogramas_hist.append(old_data)
        cronogramas_hist = cronogramas_hist[-5:]

    channels.actualizar(
        canal_id,
        cronograma_activo=json.loads(cronograma.model_dump_json()),
        cronogramas_historial=cronogramas_hist,
    )

    log.info(
        "cronograma generado | id=%s | entradas=%d | periodo=%dd",
        cronograma_id, len(entradas), periodo_dias,
    )

    telegram.notificar_cronograma_generado(
        canal=estado.nombre,
        cronograma_id=cronograma_id,
        periodo_dias=periodo_dias,
        total_videos=len(entradas),
        fase=madurez["fase"],
        primer_video=entradas[0].titulo_sugerido if entradas else None,
    )

    return {
        "cronograma_id": cronograma_id,
        "canal_id": canal_id,
        "periodo_dias": periodo_dias,
        "frecuencia_semanal": frecuencia_semanal,
        "total_videos": len(entradas),
        "fecha_inicio": fecha_inicio.strftime("%Y-%m-%d"),
        "fecha_fin": fecha_fin.strftime("%Y-%m-%d"),
        "madurez_canal": madurez["fase"],
        "madurez_detalle": madurez,
        "estrategia": resultado.get("estrategia_general", ""),
        "cadencia": resultado.get("cadencia_recomendada", ""),
        "distribucion_tipos": resultado.get("distribucion_tipos", {}),
        "entradas_resumen": [
            {
                "dia": e.dia,
                "fecha": e.fecha_programada,
                "titulo": e.titulo_sugerido,
                "tipo": e.tipo_contenido,
                "prioridad": e.prioridad,
                "potencial_viral": e.potencial_viral,
            }
            for e in entradas
        ],
    }


# ── Pre-analisis para revision de vigencia ────────────────────

_STOPWORDS = {
    "como", "para", "esto", "este", "esta", "esos", "esas",
    "que", "los", "las", "una", "uno", "con", "por", "del",
    "mas", "pero", "todo", "todos", "sobre", "entre", "desde",
    "hasta", "cada", "cuando", "donde", "puede", "pueden",
    "hacer", "tiene", "tienen", "mejor", "mejores", "peor",
    "the", "and", "for", "you", "your", "that", "this", "with",
    "how", "what", "top", "best", "worst",
}

_SUFIJOS = ["iones", "cion", "ando", "endo", "mente", "ores", "ador", "ados", "idas", "idad", "ismo", "ista", "able", "ible"]

_VARIANTES = {
    "cripto": "crypto", "crypto": "crypto",
    "criptomoneda": "crypto", "criptomonedas": "crypto", "cryptocurrency": "crypto",
    "bitcoin": "btc", "btc": "btc",
    "ethereum": "eth", "eth": "eth",
    "trading": "trade", "trader": "trade", "traders": "trade", "trade": "trade",
    "invertir": "inversion", "inversion": "inversion", "inversiones": "inversion",
    "inversor": "inversion", "inversors": "inversion", "investing": "inversion",
    "investment": "inversion",
    "dinero": "dinero", "money": "dinero", "plata": "dinero",
    "ganar": "ganar", "ganancias": "ganar", "ganancia": "ganar",
    "negocio": "negocio", "negocios": "negocio", "business": "negocio",
    "finanza": "finanza", "finanzas": "finanza", "finance": "finanza", "financial": "finanza",
    "emprender": "emprend", "emprendimiento": "emprend", "emprendedor": "emprend",
    "tecnologia": "tech", "technology": "tech", "tech": "tech",
    "inteligencia": "intel", "intelligence": "intel",
    "artificial": "ai_ml", "ai": "ai_ml",
    "programar": "code", "programacion": "code", "coding": "code", "programming": "code",
    "marketing": "mktg", "mercadeo": "mktg",
    "inmobiliario": "realestate", "inmobiliaria": "realestate", "inmobiliarias": "realestate",
    "bienes raices": "realestate", "real estate": "realestate",
    "fitness": "fitness", "ejercicio": "fitness", "ejercicios": "fitness", "workout": "fitness",
    "salud": "health", "health": "health", "saludable": "health",
    "receta": "cocina", "recetas": "cocina", "cocina": "cocina", "cocinar": "cocina",
    "cooking": "cocina", "recipe": "cocina", "recipes": "cocina",
    "principiante": "beginner", "principiantes": "beginner", "novato": "beginner",
    "novatos": "beginner", "beginner": "beginner", "beginners": "beginner",
    "error": "error", "errores": "error", "mistakes": "error", "mistake": "error",
    "secreto": "secreto", "secretos": "secreto", "secret": "secreto", "secrets": "secreto",
    "tutorial": "tutorial", "tutoriales": "tutorial", "guia": "tutorial", "guide": "tutorial",
}


def _normalizar_palabra(palabra: str) -> str:
    p = palabra.lower().strip(".,;:!?()[]\"'")
    if p in _VARIANTES:
        return _VARIANTES[p]
    for suf in _SUFIJOS:
        if len(p) > len(suf) + 3 and p.endswith(suf):
            raiz = p[:-len(suf)]
            if raiz in _VARIANTES:
                return _VARIANTES[raiz]
            return raiz
    if p.endswith("es") and len(p) > 4:
        singular = p[:-2]
        if singular in _VARIANTES:
            return _VARIANTES[singular]
    if p.endswith("s") and len(p) > 4:
        singular = p[:-1]
        if singular in _VARIANTES:
            return _VARIANTES[singular]
    return p


def _extraer_tokens(texto: str) -> set[str]:
    palabras = texto.lower().split()
    tokens = set()
    for p in palabras:
        norm = _normalizar_palabra(p)
        if len(norm) > 2 and norm not in _STOPWORDS:
            tokens.add(norm)
    return tokens


def _detectar_solapamiento_competidores(entrada, competidores) -> dict:
    """Detecta si algun competidor publico algo similar al tema planeado."""
    tokens_entrada = _extraer_tokens(entrada.tema + " " + entrada.titulo_sugerido)

    solapamientos = []
    for comp in competidores:
        for v in comp.videos_recientes[:10]:
            if not v.publicado_en:
                continue
            dias_desde = (datetime.utcnow() - v.publicado_en).days
            if dias_desde > 14:
                continue

            tokens_video = _extraer_tokens(v.titulo)
            coincidencias = len(tokens_entrada & tokens_video)
            relevancia = coincidencias / len(tokens_entrada) if tokens_entrada else 0

            if relevancia >= 0.3 or coincidencias >= 3:
                solapamientos.append({
                    "competidor": comp.nombre,
                    "titulo": v.titulo,
                    "vistas": v.vistas,
                    "dias_desde_publicacion": dias_desde,
                    "relevancia": round(relevancia, 2),
                    "tokens_comunes": list(tokens_entrada & tokens_video)[:5],
                })

    solapamientos.sort(key=lambda x: x["relevancia"], reverse=True)

    nivel = "ninguno"
    if solapamientos:
        top = solapamientos[0]
        if top["relevancia"] >= 0.6 and top["dias_desde_publicacion"] <= 3:
            nivel = "alto"
        elif top["relevancia"] >= 0.4 or top["dias_desde_publicacion"] <= 5:
            nivel = "medio"
        else:
            nivel = "bajo"

    return {
        "nivel": nivel,
        "solapamientos": solapamientos[:5],
    }


def _analizar_performance_ultimo_video(cronograma, estado) -> dict:
    """Analiza si el ultimo video producido tuvo performance excepcional o pobre."""
    producidos = [
        e for e in cronograma.entradas
        if e.status in ("publicado",)
    ]
    if not producidos:
        return {"senal": "sin_datos", "detalle": "Ningun video del cronograma publicado aun"}

    ultimo = producidos[-1]
    titulo_ultimo = ultimo.titulo_final or ultimo.titulo_sugerido

    performance_match = None
    for p in reversed(estado.performance_historial):
        if p.get("titulo", "").lower() == titulo_ultimo.lower():
            performance_match = p
            break

    if not performance_match:
        return {
            "senal": "sin_datos",
            "detalle": f"Video '{titulo_ultimo}' publicado pero sin datos de performance aun",
            "titulo": titulo_ultimo,
        }

    ratio = performance_match.get("ratio_vs_promedio", 100)
    vistas = performance_match.get("vistas", 0)

    if ratio >= 200:
        senal = "excepcional"
        detalle = (
            f"'{titulo_ultimo}' obtuvo {vistas:,} vistas ({ratio}% vs promedio). "
            f"OPORTUNIDAD: un follow-up inmediato podria capitalizar el momentum."
        )
    elif ratio >= 130:
        senal = "bueno"
        detalle = (
            f"'{titulo_ultimo}' obtuvo {vistas:,} vistas ({ratio}% vs promedio). "
            f"Buen rendimiento, el tema/formato resuena con la audiencia."
        )
    elif ratio < 50:
        senal = "pobre"
        detalle = (
            f"'{titulo_ultimo}' obtuvo solo {vistas:,} vistas ({ratio}% vs promedio). "
            f"PRECAUCION: evitar tema/formato similar en el siguiente video."
        )
    else:
        senal = "normal"
        detalle = f"'{titulo_ultimo}' obtuvo {vistas:,} vistas ({ratio}% vs promedio). Rendimiento normal."

    return {
        "senal": senal,
        "detalle": detalle,
        "titulo": titulo_ultimo,
        "vistas": vistas,
        "ratio_vs_promedio": ratio,
        "tipo_contenido": ultimo.tipo_contenido,
        "formato": ultimo.formato,
    }


def _buscar_trending_fresco(nicho: str, subnicho: str) -> dict:
    """Busca tendencias frescas via web para detectar eventos urgentes."""
    try:
        from shared.web_search import buscar

        query = subnicho or nicho
        resultados = buscar(f"{query} youtube trending hoy 2025 2026", max_resultados=5)
        if not resultados:
            return {"disponible": False, "texto": "(sin resultados de busqueda)"}

        lineas = []
        for r in resultados:
            lineas.append(f"- {r['titulo']}: {r['resumen'][:150]}")

        return {
            "disponible": True,
            "texto": "\n".join(lineas),
            "total_resultados": len(resultados),
        }
    except Exception as exc:
        log.warning("busqueda trending fresca no disponible: %s", exc)
        return {"disponible": False, "texto": f"(busqueda no disponible: {exc})"}


def _evaluar_frescura_datos(estado, cronograma) -> dict:
    """Evalua que tan actualizados estan los datos de inteligencia."""
    ahora = datetime.utcnow()

    frescura = {}

    if estado.competidores_actualizados_en:
        dias = (ahora - estado.competidores_actualizados_en).days
        frescura["competidores_dias"] = dias
        frescura["competidores_estado"] = (
            "frescos" if dias <= 2 else "aceptables" if dias <= 5 else "desactualizados"
        )
    else:
        frescura["competidores_dias"] = None
        frescura["competidores_estado"] = "sin_datos"

    if estado.escaneado_en:
        dias = (ahora - estado.escaneado_en).days
        frescura["canal_dias"] = dias
        frescura["canal_estado"] = (
            "frescos" if dias <= 2 else "aceptables" if dias <= 5 else "desactualizados"
        )
    else:
        frescura["canal_dias"] = None
        frescura["canal_estado"] = "sin_datos"

    if cronograma.generado_en:
        dias = (ahora - cronograma.generado_en).days
        frescura["cronograma_dias"] = dias
        frescura["cronograma_estado"] = (
            "reciente" if dias <= 3 else "aceptable" if dias <= 7 else "antiguo"
        )
    else:
        frescura["cronograma_dias"] = None
        frescura["cronograma_estado"] = "sin_datos"

    estados = [
        frescura.get("competidores_estado", "sin_datos"),
        frescura.get("canal_estado", "sin_datos"),
    ]
    if "desactualizados" in estados or "sin_datos" in estados:
        frescura["nivel_general"] = "desactualizados"
    elif all(e == "frescos" for e in estados):
        frescura["nivel_general"] = "frescos"
    else:
        frescura["nivel_general"] = "aceptables"

    return frescura


def _contexto_entradas_futuras(cronograma, dia_actual: int) -> str:
    """Muestra las proximas entradas del cronograma para evaluar impacto en cascada."""
    futuras = [
        e for e in cronograma.entradas
        if e.dia > dia_actual and e.status == "pendiente"
    ]
    if not futuras:
        return "(no hay entradas pendientes despues de esta)"

    lineas = []
    for e in futuras[:5]:
        lineas.append(
            f"- Dia {e.dia} ({e.fecha_programada}): \"{e.titulo_sugerido}\" "
            f"[{e.tipo_contenido}] {e.formato}"
        )
    restantes = len(futuras) - 5
    if restantes > 0:
        lineas.append(f"  ... y {restantes} entradas mas")
    return "\n".join(lineas)


def _slots_disponibles_para_reubicacion(cronograma, dia_actual: int) -> list[str]:
    """Encuentra fechas sin video asignado para reubicar una entrada sustituida."""
    fechas_ocupadas = {e.fecha_programada for e in cronograma.entradas}

    fecha_inicio = datetime.fromisoformat(cronograma.fecha_inicio)
    fecha_fin = datetime.fromisoformat(cronograma.fecha_fin)

    slots = []
    fecha = fecha_inicio
    while fecha <= fecha_fin:
        fecha_str = fecha.strftime("%Y-%m-%d")
        if fecha_str not in fechas_ocupadas and fecha > datetime.utcnow():
            slots.append(f"{fecha_str} ({DIAS_SEMANA[fecha.weekday()]})")
        fecha += timedelta(days=1)

    return slots[:5]


# ── Modo REVISAR ──────────────────────────────────────────────

def _revisar_entrada(canal_id: str, dia: int) -> dict:
    estado = channels.leer(canal_id)
    perfil = estado.perfil

    if not estado.cronograma_activo:
        raise ValueError("No hay cronograma activo para este canal")

    cronograma = estado.cronograma_activo

    entrada = None
    entrada_idx = None
    for i, e in enumerate(cronograma.entradas):
        if e.dia == dia:
            entrada = e
            entrada_idx = i
            break

    if entrada is None or entrada_idx is None:
        dias_disponibles = [e.dia for e in cronograma.entradas]
        raise ValueError(
            f"No se encontro la entrada dia {dia}. "
            f"Dias disponibles: {dias_disponibles}"
        )

    if entrada.status not in ("pendiente", "en_revision"):
        raise ValueError(
            f"La entrada dia {dia} tiene status '{entrada.status}', "
            f"solo se pueden revisar entradas 'pendiente' o 'en_revision'"
        )

    log.info(
        "iniciando revision de vigencia | dia=%d | canal=%s | titulo=%s",
        dia, canal_id, entrada.titulo_sugerido,
    )

    # ── 1. SOLAPAMIENTO CON COMPETIDORES ──
    solapamiento = _detectar_solapamiento_competidores(
        entrada, estado.competidores,
    )
    solapamiento_texto = f"Nivel: {solapamiento['nivel'].upper()}"
    if solapamiento["solapamientos"]:
        for s in solapamiento["solapamientos"]:
            solapamiento_texto += (
                f"\n  - {s['competidor']}: \"{s['titulo']}\" "
                f"({s['vistas']:,} vistas, hace {s['dias_desde_publicacion']}d, "
                f"relevancia {s['relevancia']:.0%})"
            )
    else:
        solapamiento_texto += "\n  Ningun competidor ha publicado contenido similar reciente."

    # ── 2. SENAL DE PERFORMANCE DEL ULTIMO VIDEO ──
    perf_ultimo = _analizar_performance_ultimo_video(cronograma, estado)
    perf_texto = f"Senal: {perf_ultimo['senal'].upper()}\n  {perf_ultimo['detalle']}"
    if perf_ultimo["senal"] in ("excepcional", "pobre") and perf_ultimo.get("tipo_contenido"):
        perf_texto += (
            f"\n  Tipo del video: {perf_ultimo['tipo_contenido']} | "
            f"Formato: {perf_ultimo.get('formato', '?')}"
        )

    # ── 3. TENDENCIAS FRESCAS (busqueda web en tiempo real) ──
    nicho = perfil.subnicho_principal or perfil.nicho_principal or ""
    trending_fresco = _buscar_trending_fresco(nicho, perfil.subnicho_principal)

    # ── 4. FRESCURA DE DATOS ──
    frescura = _evaluar_frescura_datos(estado, cronograma)
    frescura_texto = (
        f"Nivel general: {frescura['nivel_general'].upper()}\n"
        f"  Competidores: {frescura.get('competidores_estado', '?')} "
        f"(actualizados hace {frescura.get('competidores_dias', '?')} dias)\n"
        f"  Canal: {frescura.get('canal_estado', '?')} "
        f"(escaneado hace {frescura.get('canal_dias', '?')} dias)\n"
        f"  Cronograma: {frescura.get('cronograma_estado', '?')} "
        f"(generado hace {frescura.get('cronograma_dias', '?')} dias)"
    )

    # ── 5. ENTRADAS FUTURAS (impacto en cascada) ──
    futuras_texto = _contexto_entradas_futuras(cronograma, dia)

    # ── 6. SLOTS DISPONIBLES PARA REUBICACION ──
    slots = _slots_disponibles_para_reubicacion(cronograma, dia)
    slots_texto = ", ".join(slots) if slots else "(no hay slots disponibles)"

    # ── 7. Actividad reciente de competidores (completa) ──
    actividad_comp = []
    for comp in estado.competidores[:5]:
        recientes = []
        for v in comp.videos_recientes[:8]:
            if not v.publicado_en:
                continue
            dias = (datetime.utcnow() - v.publicado_en).days
            recientes.append(
                f"\"{v.titulo}\" ({v.vistas:,} vistas, hace {dias}d)"
            )
        if recientes:
            actividad_comp.append(
                f"- {comp.nombre} ({comp.suscriptores or '?'} subs):\n"
                f"    {', '.join(recientes[:5])}"
            )

    # ── 8. Performance historial del canal ──
    performance_reciente = []
    for p in estado.performance_historial[-8:]:
        ctr_info = f", CTR {p['ctr']}%" if p.get("ctr") else ""
        performance_reciente.append(
            f"- \"{p.get('titulo', '?')}\" -> {p.get('vistas', 0):,} vistas, "
            f"ratio {p.get('ratio_vs_promedio', '?')}% vs promedio{ctr_info}"
        )

    # ── 9. Contexto del cronograma ──
    dias_desde_gen = "?"
    if cronograma.generado_en:
        dias_desde_gen = (datetime.utcnow() - cronograma.generado_en).days

    progreso_plan = (
        f"{cronograma.videos_publicados}/{cronograma.total_videos} publicados, "
        f"{cronograma.videos_ajustados} ajustados"
    )
    entradas_pendientes = sum(
        1 for e in cronograma.entradas if e.status == "pendiente"
    )

    # ── Construir prompt completo ──
    user_prompt = f"""ENTRADA DEL CRONOGRAMA A REVISAR:
Dia: {entrada.dia}
Fecha programada: {entrada.fecha_programada}
Titulo sugerido: {entrada.titulo_sugerido}
Tema: {entrada.tema}
Angulo: {entrada.angulo}
Tipo contenido: {entrada.tipo_contenido}
Formato: {entrada.formato}
Prioridad: {entrada.prioridad}
Potencial viral estimado: {entrada.potencial_viral}
Razon original del tema: {entrada.razon_tema}
Razon original de la fecha: {entrada.razon_fecha}
Keywords planeadas: {', '.join(entrada.keywords_recomendadas) if entrada.keywords_recomendadas else 'N/A'}
Datos de soporte originales: {json.dumps(entrada.datos_soporte, ensure_ascii=False) if entrada.datos_soporte else 'N/A'}
Ajustes previos a esta entrada: {len(entrada.ajustes_historial)} ajuste(s) anteriores

CONTEXTO DEL CRONOGRAMA:
Cronograma ID: {cronograma.cronograma_id}
Generado el: {cronograma.generado_en.isoformat() if cronograma.generado_en else '?'}
Dias desde generacion: {dias_desde_gen}
Fase del canal: {cronograma.madurez_canal or '?'}
Estrategia general del plan: {cronograma.estrategia_secuencia}
Progreso: {progreso_plan}
Entradas pendientes: {entradas_pendientes}

CANAL: {estado.nombre}
Nicho: {perfil.nicho_principal or '?'} / Subnicho: {perfil.subnicho_principal or '?'}

=== ANALISIS PRE-REVISION (datos procesados automaticamente) ===

1. ALERTA DE SOLAPAMIENTO CON COMPETIDORES:
{solapamiento_texto}

2. SENAL DE PERFORMANCE DEL ULTIMO VIDEO PRODUCIDO:
{perf_texto}

3. BUSQUEDA WEB FRESCA DE TENDENCIAS DEL NICHO (en tiempo real):
{trending_fresco['texto']}

4. FRESCURA DE LOS DATOS DE INTELIGENCIA:
{frescura_texto}

=== CONTEXTO ADICIONAL ===

VIDEOS YA PRODUCIDOS/APROBADOS DE ESTE CRONOGRAMA:
{_resumen_entradas_completadas(cronograma)}

PROXIMAS ENTRADAS DEL CRONOGRAMA (impacto en cascada):
{futuras_texto}

SLOTS DISPONIBLES PARA REUBICAR (si se sustituye y el tema original es valido):
{slots_texto}

ACTIVIDAD RECIENTE DE COMPETIDORES (completa):
{chr(10).join(actividad_comp) if actividad_comp else '(sin datos recientes de competidores)'}

TENDENCIAS ALMACENADAS DEL NICHO:
{chr(10).join(f'- {t}' for t in estado.tendencias_nicho) if estado.tendencias_nicho else '(sin tendencias almacenadas)'}

BRECHAS DE CONTENIDO VIGENTES:
{chr(10).join(f'- {b}' for b in estado.brechas_contenido) if estado.brechas_contenido else '(sin brechas)'}

HISTORIAL DE PERFORMANCE DEL CANAL (ultimos videos):
{chr(10).join(performance_reciente) if performance_reciente else '(sin datos de performance)'}

Fecha actual: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC

Evalua la vigencia de esta entrada considerando TODOS los factores pre-analizados.
Prioriza las senales fuertes: trending urgente > performance excepcional > solapamiento.
Si sustituyes y el tema original sigue siendo valido, sugiere reubicarlo."""

    user_prompt = inyectar_knowledge(user_prompt, "depto_0_inteligencia")

    resultado = generar_json_claude(SYSTEM_PROMPT_REVISAR, user_prompt)

    decision = resultado.get("decision", "proceder")
    score_vigencia = resultado.get("score_vigencia", 5.0)

    log.info(
        "revision de vigencia | dia=%d | decision=%s | score=%.1f | confianza=%.1f",
        dia, decision, score_vigencia, resultado.get("confianza", 0),
    )

    # ── Aplicar decision al cronograma ──
    if decision == "proceder":
        cronograma.entradas[entrada_idx].status = "aprobado"

    elif decision == "ajustar":
        actualizada = resultado.get("entrada_actualizada", {})
        ajuste = {
            "fecha": datetime.utcnow().isoformat(timespec="seconds"),
            "decision": "ajustar",
            "score_vigencia": score_vigencia,
            "titulo_original": entrada.titulo_sugerido,
            "titulo_nuevo": actualizada.get(
                "titulo_sugerido", entrada.titulo_sugerido,
            ),
            "tema_original": entrada.tema,
            "tema_nuevo": actualizada.get("tema", entrada.tema),
            "angulo_original": entrada.angulo,
            "angulo_nuevo": actualizada.get("angulo", entrada.angulo),
            "razon": actualizada.get("razon_ajuste", ""),
            "factores": resultado.get("factores_evaluados", {}),
        }
        e = cronograma.entradas[entrada_idx]
        e.ajustes_historial.append(ajuste)
        e.titulo_sugerido = actualizada.get(
            "titulo_sugerido", entrada.titulo_sugerido,
        )
        e.tema = actualizada.get("tema", entrada.tema)
        e.angulo = actualizada.get("angulo", entrada.angulo)
        if actualizada.get("formato"):
            e.formato = actualizada["formato"]
        if actualizada.get("keywords_recomendadas"):
            e.keywords_recomendadas = actualizada["keywords_recomendadas"]
        if actualizada.get("duracion_sugerida_min"):
            e.duracion_sugerida_min = actualizada["duracion_sugerida_min"]
        e.status = "aprobado"
        cronograma.videos_ajustados += 1

    elif decision == "sustituir":
        alternativa = resultado.get("alternativa") or {}
        reubicar = resultado.get("reubicar_original", False)
        fecha_reubicacion = resultado.get("fecha_reubicacion_sugerida")

        ajuste = {
            "fecha": datetime.utcnow().isoformat(timespec="seconds"),
            "decision": "sustituir",
            "score_vigencia": score_vigencia,
            "titulo_original": entrada.titulo_sugerido,
            "tema_original": entrada.tema,
            "titulo_nuevo": alternativa.get("titulo_sugerido", ""),
            "tema_nuevo": alternativa.get("tema", ""),
            "razon": alternativa.get("razon", ""),
            "factores": resultado.get("factores_evaluados", {}),
            "reubicado": reubicar,
            "fecha_reubicacion": fecha_reubicacion,
        }

        e = cronograma.entradas[entrada_idx]
        e.ajustes_historial.append(ajuste)
        e.titulo_sugerido = alternativa.get(
            "titulo_sugerido", entrada.titulo_sugerido,
        )
        e.tema = alternativa.get("tema", entrada.tema)
        e.angulo = alternativa.get("angulo", entrada.angulo)
        e.tipo_contenido = alternativa.get(
            "tipo_contenido", entrada.tipo_contenido,
        )
        if alternativa.get("formato"):
            e.formato = alternativa["formato"]
        if alternativa.get("duracion_sugerida_min"):
            e.duracion_sugerida_min = alternativa["duracion_sugerida_min"]
        e.status = "aprobado"
        cronograma.videos_ajustados += 1

        # ── Reubicar el tema original si Claude lo recomienda ──
        if reubicar and fecha_reubicacion:
            nueva_entrada = EntradaCronograma(
                dia=max(e.dia for e in cronograma.entradas) + 1,
                fecha_programada=fecha_reubicacion.split(" ")[0],
                titulo_sugerido=entrada.titulo_sugerido,
                tema=entrada.tema,
                angulo=entrada.angulo,
                tipo_contenido=entrada.tipo_contenido,
                formato=entrada.formato,
                duracion_sugerida_min=entrada.duracion_sugerida_min,
                prioridad=entrada.prioridad,
                potencial_viral=entrada.potencial_viral,
                razon_fecha=f"Reubicado desde dia {entrada.dia}: {alternativa.get('razon', '')}",
                razon_tema=entrada.razon_tema,
                keywords_recomendadas=list(entrada.keywords_recomendadas),
                datos_soporte=dict(entrada.datos_soporte),
                ajustes_historial=[{
                    "fecha": datetime.utcnow().isoformat(timespec="seconds"),
                    "decision": "reubicado",
                    "dia_original": entrada.dia,
                    "fecha_original": entrada.fecha_programada,
                    "razon": f"Sustituido por: {alternativa.get('titulo_sugerido', '?')}",
                }],
            )
            cronograma.entradas.append(nueva_entrada)
            cronograma.total_videos += 1
            log.info(
                "entrada reubicada | dia_original=%d | nueva_fecha=%s | titulo=%s",
                entrada.dia, fecha_reubicacion, entrada.titulo_sugerido,
            )

    # ── Persistir cambios ──
    channels.actualizar(
        canal_id,
        cronograma_activo=json.loads(cronograma.model_dump_json()),
    )

    log.info(
        "revision completada | dia=%d | decision=%s | score_vigencia=%.1f | "
        "solapamiento=%s | performance=%s",
        dia, decision, score_vigencia,
        solapamiento["nivel"], perf_ultimo["senal"],
    )

    telegram.notificar_revision_vigencia(
        canal=estado.nombre,
        dia=dia,
        titulo=cronograma.entradas[entrada_idx].titulo_sugerido,
        decision=decision,
        score=score_vigencia,
    )

    return {
        "canal_id": canal_id,
        "cronograma_id": cronograma.cronograma_id,
        "dia": dia,
        "decision": decision,
        "confianza": resultado.get("confianza"),
        "score_vigencia": score_vigencia,
        "razon": resultado.get("razon", ""),
        "factores_evaluados": resultado.get("factores_evaluados", {}),
        "cambios_detectados": resultado.get("cambios_detectados", []),
        "pre_analisis": {
            "solapamiento": solapamiento,
            "performance_ultimo": perf_ultimo,
            "frescura_datos": frescura,
            "trending_disponible": trending_fresco["disponible"],
        },
        "titulo_final": cronograma.entradas[entrada_idx].titulo_sugerido,
        "entrada_actualizada": resultado.get("entrada_actualizada"),
        "alternativa": resultado.get("alternativa"),
        "reubicado": resultado.get("reubicar_original", False),
        "fecha_reubicacion": resultado.get("fecha_reubicacion_sugerida"),
    }


# ── Modo ADAPTAR ──────────────────────────────────────────────

SYSTEM_PROMPT_FOLLOWUP = """Eres un estratega de contenido de YouTube. Un video acaba de tener
un rendimiento EXCEPCIONAL y necesitas generar un follow-up para capitalizar el momentum.

El follow-up debe:
- Estar tematicamente RELACIONADO al video exitoso (no ser identico)
- Ofrecer un NUEVO angulo que complemente el original
- Ser producible rapidamente (priorizar formatos agiles)
- Aprovechar que el algoritmo esta empujando contenido del canal

Tipos de follow-up efectivos:
- "Parte 2" o profundizacion en un aspecto mencionado
- Respuesta a comentarios/preguntas del video exitoso
- El mismo tema desde perspectiva opuesta
- Caso de estudio o ejemplo practico de lo que se explico
- Version actualizada o expandida

SIEMPRE respondes en JSON valido con este formato exacto:
{
  "titulo_sugerido": "titulo del follow-up clickeable y relacionado",
  "tema": "descripcion del tema (1-2 frases)",
  "angulo": "como se diferencia del video original",
  "tipo_contenido": "follow_up",
  "formato": "tutorial|listicle|storytime|comparacion|caso_estudio|reaccion|explicacion",
  "duracion_sugerida_min": 10,
  "keywords_recomendadas": ["kw1", "kw2", "kw3"],
  "conexion_con_original": "como este video se conecta con el exitoso (para mencionarlo/linkear)",
  "razon": "por que este follow-up va a funcionar (basado en datos)"
}"""


def _adaptar_cronograma(canal_id: str, senal: dict) -> dict:
    estado = channels.leer(canal_id)

    if not estado.cronograma_activo:
        return {
            "canal_id": canal_id,
            "accion": "sin_cronograma",
            "detalle": "No hay cronograma activo, la senal se registra pero no se puede adaptar.",
        }

    cronograma = estado.cronograma_activo
    tipo_senal = senal.get("tipo_senal", "")
    titulo_video = senal.get("video_titulo", "")
    ratio = senal.get("ratio_vs_promedio", 100)

    log.info(
        "adaptando cronograma | canal=%s | senal=%s | video=%s | ratio=%s%%",
        canal_id, tipo_senal, titulo_video, ratio,
    )

    if tipo_senal == "excepcional":
        return _inyectar_followup(canal_id, estado, cronograma, senal)
    elif tipo_senal == "pobre":
        return _flagear_entradas_similares(canal_id, estado, cronograma, senal)
    elif tipo_senal == "ctr_bajo_retencion_alta":
        return _reforzar_empaque(canal_id, cronograma, senal)
    else:
        return {
            "canal_id": canal_id,
            "accion": "senal_no_reconocida",
            "tipo_senal": tipo_senal,
        }


def _inyectar_followup(canal_id: str, estado, cronograma, senal: dict) -> dict:
    """Genera un follow-up con Claude e inyecta en el proximo slot disponible."""
    perfil = estado.perfil
    titulo_exitoso = senal.get("video_titulo", "")

    # Encontrar slot disponible en los proximos 3 dias
    fechas_ocupadas = {e.fecha_programada for e in cronograma.entradas}
    ahora = datetime.utcnow()
    slot_fecha = None
    for i in range(1, 5):
        candidata = (ahora + timedelta(days=i)).strftime("%Y-%m-%d")
        if candidata not in fechas_ocupadas:
            slot_fecha = candidata
            break

    if not slot_fecha:
        log.info("no hay slot disponible en los proximos 4 dias para follow-up")
        return {
            "canal_id": canal_id,
            "accion": "sin_slot",
            "detalle": "No hay slot disponible en los proximos 4 dias. "
                       "La senal se registra para la revision de vigencia.",
        }

    # Entradas ya en el cronograma (para no duplicar)
    titulos_existentes = [e.titulo_sugerido for e in cronograma.entradas]

    metricas_texto = (
        f"Vistas: {senal.get('vistas', '?'):,} | "
        f"CTR: {senal.get('ctr', '?')}% | "
        f"Retencion: {senal.get('retencion', '?')}% | "
        f"Engagement: {senal.get('engagement', '?')}% | "
        f"Ratio vs promedio: {senal.get('ratio_vs_promedio', '?')}%"
    )

    user_prompt = f"""VIDEO EXITOSO QUE NECESITA FOLLOW-UP:
Titulo: "{titulo_exitoso}"
Nicho: {perfil.nicho_principal or senal.get('video_nicho', '?')}
Subnicho: {perfil.subnicho_principal or '?'}
Checkpoint: {senal.get('checkpoint', '?')}

Metricas:
{metricas_texto}

FECHA PARA EL FOLLOW-UP: {slot_fecha} ({DIAS_SEMANA[datetime.fromisoformat(slot_fecha).weekday()]})

VIDEOS YA PLANEADOS EN EL CRONOGRAMA (no duplicar):
{chr(10).join(f'- {t}' for t in titulos_existentes)}

Patrones de titulo exitosos del canal:
{', '.join(perfil.patrones_titulo_exitosos) if perfil.patrones_titulo_exitosos else 'N/A'}

Genera un follow-up que capitalice el momentum de "{titulo_exitoso}".
El follow-up debe poder producirse rapidamente (1-2 dias)."""

    user_prompt = inyectar_knowledge(user_prompt, "depto_0_inteligencia")
    resultado = generar_json_claude(SYSTEM_PROMPT_FOLLOWUP, user_prompt)

    # Crear entrada de follow-up
    nuevo_dia = max(e.dia for e in cronograma.entradas) + 1
    followup = EntradaCronograma(
        dia=nuevo_dia,
        fecha_programada=slot_fecha,
        titulo_sugerido=resultado.get("titulo_sugerido", f"Follow-up: {titulo_exitoso}"),
        tema=resultado.get("tema", ""),
        angulo=resultado.get("angulo", ""),
        tipo_contenido="follow_up",
        formato=resultado.get("formato", "explicacion"),
        duracion_sugerida_min=resultado.get("duracion_sugerida_min", 10),
        prioridad="alta",
        potencial_viral=min(senal.get("ratio_vs_promedio", 100) / 25, 10.0),
        razon_fecha=f"Follow-up urgente de '{titulo_exitoso}' ({senal.get('ratio_vs_promedio', '?')}% vs promedio)",
        razon_tema=resultado.get("razon", ""),
        keywords_recomendadas=resultado.get("keywords_recomendadas", []),
        datos_soporte={
            "fuente": "performance_tracker",
            "video_original": titulo_exitoso,
            "ratio": senal.get("ratio_vs_promedio"),
            "checkpoint": senal.get("checkpoint"),
            "conexion": resultado.get("conexion_con_original", ""),
        },
    )

    cronograma.entradas.append(followup)
    cronograma.total_videos += 1

    channels.actualizar(
        canal_id,
        cronograma_activo=json.loads(cronograma.model_dump_json()),
    )

    log.info(
        "follow-up inyectado | dia=%d | fecha=%s | titulo=%s",
        nuevo_dia, slot_fecha, followup.titulo_sugerido,
    )

    telegram.notificar_followup_inyectado(
        canal=estado.nombre,
        video_exitoso=titulo_exitoso,
        ratio=senal.get("ratio_vs_promedio"),
        followup_titulo=followup.titulo_sugerido,
        followup_fecha=slot_fecha,
    )

    return {
        "canal_id": canal_id,
        "cronograma_id": cronograma.cronograma_id,
        "accion": "followup_inyectado",
        "video_exitoso": titulo_exitoso,
        "ratio_vs_promedio": senal.get("ratio_vs_promedio"),
        "followup": {
            "dia": nuevo_dia,
            "fecha": slot_fecha,
            "titulo": followup.titulo_sugerido,
            "tema": followup.tema,
            "angulo": followup.angulo,
            "formato": followup.formato,
        },
    }


def _flagear_entradas_similares(canal_id: str, estado, cronograma, senal: dict) -> dict:
    """Marca entradas pendientes con tema/formato similar al video pobre para revision."""
    titulo_pobre = senal.get("video_titulo", "")
    nicho_pobre = senal.get("video_nicho", "")

    tokens_video = _extraer_tokens(titulo_pobre + " " + nicho_pobre)

    flagged = []
    for i, e in enumerate(cronograma.entradas):
        if e.status != "pendiente":
            continue

        tokens_entrada = _extraer_tokens(e.titulo_sugerido + " " + e.tema)

        overlap = len(tokens_video & tokens_entrada)
        total = max(len(tokens_video), 1)

        if overlap >= 3 or (overlap / total) >= 0.3:
            cronograma.entradas[i].status = "en_revision"
            cronograma.entradas[i].ajustes_historial.append({
                "fecha": datetime.utcnow().isoformat(timespec="seconds"),
                "decision": "flagged_por_performance",
                "video_pobre": titulo_pobre,
                "ratio": senal.get("ratio_vs_promedio"),
                "razon": (
                    f"Video similar '{titulo_pobre}' tuvo {senal.get('ratio_vs_promedio', '?')}% "
                    f"vs promedio. Esta entrada comparte tematica y necesita revision de angulo."
                ),
            })
            flagged.append({
                "dia": e.dia,
                "fecha": e.fecha_programada,
                "titulo": e.titulo_sugerido,
                "overlap_palabras": overlap,
            })
            log.info(
                "entrada flagged | dia=%d | titulo=%s | overlap=%d palabras",
                e.dia, e.titulo_sugerido, overlap,
            )

    if flagged:
        channels.actualizar(
            canal_id,
            cronograma_activo=json.loads(cronograma.model_dump_json()),
        )
        telegram.notificar_entradas_flagged(
            canal=estado.nombre,
            video_pobre=titulo_pobre,
            ratio=senal.get("ratio_vs_promedio"),
            total_flagged=len(flagged),
        )

    return {
        "canal_id": canal_id,
        "cronograma_id": cronograma.cronograma_id,
        "accion": "entradas_flagged",
        "video_pobre": titulo_pobre,
        "ratio_vs_promedio": senal.get("ratio_vs_promedio"),
        "entradas_flagged": flagged,
        "total_flagged": len(flagged),
        "detalle": (
            f"{len(flagged)} entrada(s) marcada(s) para revision por similitud con "
            f"video de bajo rendimiento '{titulo_pobre}'"
            if flagged else
            "No se encontraron entradas similares al video de bajo rendimiento"
        ),
    }


def _reforzar_empaque(canal_id: str, cronograma, senal: dict) -> dict:
    """Agrega notas a proximas entradas para reforzar estrategia de titulo/thumbnail."""
    titulo_video = senal.get("video_titulo", "")
    entradas_anotadas = []

    for i, e in enumerate(cronograma.entradas):
        if e.status != "pendiente":
            continue
        if len(entradas_anotadas) >= 3:
            break

        cronograma.entradas[i].ajustes_historial.append({
            "fecha": datetime.utcnow().isoformat(timespec="seconds"),
            "decision": "refuerzo_empaque",
            "razon": (
                f"Video '{titulo_video}' tuvo CTR {senal.get('ctr', '?')}% "
                f"pero retencion {senal.get('retencion', '?')}%. "
                f"Buen contenido, mal empaque. Reforzar titulo/thumbnail en esta entrada."
            ),
        })
        entradas_anotadas.append({
            "dia": e.dia,
            "titulo": e.titulo_sugerido,
        })

    if entradas_anotadas:
        channels.actualizar(
            canal_id,
            cronograma_activo=json.loads(cronograma.model_dump_json()),
        )

    log.info(
        "empaque reforzado en %d entradas | video=%s | ctr=%s%% | retencion=%s%%",
        len(entradas_anotadas), titulo_video,
        senal.get("ctr", "?"), senal.get("retencion", "?"),
    )

    return {
        "canal_id": canal_id,
        "cronograma_id": cronograma.cronograma_id,
        "accion": "empaque_reforzado",
        "video_con_mal_empaque": titulo_video,
        "ctr": senal.get("ctr"),
        "retencion": senal.get("retencion"),
        "entradas_anotadas": entradas_anotadas,
        "detalle": (
            f"{len(entradas_anotadas)} entrada(s) anotada(s) para reforzar "
            f"estrategia de titulo/thumbnail basado en aprendizaje de '{titulo_video}'"
        ),
    }


# ── Modo GESTIONAR (ciclo de vida de entradas) ───────────────

_TRANSICIONES_VALIDAS: dict[str, set[str]] = {
    "pendiente": {"en_revision", "aprobado", "en_produccion", "pospuesto", "cancelado"},
    "en_revision": {"aprobado", "pospuesto", "cancelado"},
    "aprobado": {"en_produccion", "pospuesto", "cancelado"},
    "en_produccion": {"publicado", "cancelado"},
    "publicado": set(),
    "pospuesto": {"pendiente", "cancelado"},
    "cancelado": set(),
}


def _gestionar_entrada(canal_id: str, dia: int, nuevo_status: str, datos: dict) -> dict:
    estado = channels.leer(canal_id)

    if not estado.cronograma_activo:
        raise ValueError("No hay cronograma activo para este canal")

    cronograma = estado.cronograma_activo

    entrada = None
    entrada_idx = None
    for i, e in enumerate(cronograma.entradas):
        if e.dia == dia:
            entrada = e
            entrada_idx = i
            break

    if entrada is None or entrada_idx is None:
        dias_disponibles = [e.dia for e in cronograma.entradas]
        raise ValueError(
            f"No se encontro la entrada dia {dia}. Disponibles: {dias_disponibles}"
        )

    status_actual = entrada.status
    validos = _TRANSICIONES_VALIDAS.get(status_actual, set())

    if nuevo_status not in validos:
        raise ValueError(
            f"Transicion invalida: '{status_actual}' -> '{nuevo_status}'. "
            f"Transiciones validas desde '{status_actual}': {sorted(validos) if validos else 'ninguna (estado final)'}"
        )

    e = cronograma.entradas[entrada_idx]
    status_anterior = e.status

    # ── Aplicar transicion ──
    e.status = nuevo_status
    e.ajustes_historial.append({
        "fecha": datetime.utcnow().isoformat(timespec="seconds"),
        "decision": f"transicion_{nuevo_status}",
        "status_anterior": status_anterior,
        "status_nuevo": nuevo_status,
        "razon": datos.get("razon", ""),
    })

    # ── Acciones especificas por status ──
    if nuevo_status == "en_produccion":
        proyecto_id = datos.get("proyecto_id")
        if proyecto_id:
            e.proyecto_id = proyecto_id

    elif nuevo_status == "publicado":
        titulo_final = datos.get("titulo_final")
        if titulo_final:
            e.titulo_final = titulo_final
        cronograma.videos_publicados += 1

        # Verificar si el cronograma esta completado
        pendientes = sum(
            1 for ent in cronograma.entradas
            if ent.status in ("pendiente", "en_revision", "aprobado", "en_produccion")
        )
        if pendientes == 0:
            cronograma.status = "completado"
            log.info("cronograma %s completado", cronograma.cronograma_id)

    elif nuevo_status == "pospuesto":
        nueva_fecha = datos.get("nueva_fecha")
        if nueva_fecha:
            e.ajustes_historial[-1]["fecha_original"] = e.fecha_programada
            e.ajustes_historial[-1]["nueva_fecha"] = nueva_fecha
            e.fecha_programada = nueva_fecha

    elif nuevo_status == "cancelado":
        cronograma.total_videos = sum(
            1 for ent in cronograma.entradas
            if ent.status not in ("cancelado",)
        )

    # ── Persistir ──
    channels.actualizar(
        canal_id,
        cronograma_activo=json.loads(cronograma.model_dump_json()),
    )

    log.info(
        "transicion | dia=%d | %s -> %s | titulo=%s",
        dia, status_anterior, nuevo_status, e.titulo_sugerido,
    )

    return {
        "canal_id": canal_id,
        "cronograma_id": cronograma.cronograma_id,
        "dia": dia,
        "titulo": e.titulo_sugerido,
        "status_anterior": status_anterior,
        "status_nuevo": nuevo_status,
        "progreso": _calcular_progreso(cronograma),
    }


def _calcular_progreso(cronograma) -> dict:
    conteos = Counter(e.status for e in cronograma.entradas)
    total = len(cronograma.entradas)
    activas = total - conteos.get("cancelado", 0)

    publicados = conteos.get("publicado", 0)
    pct = round((publicados / activas * 100), 1) if activas > 0 else 0

    return {
        "total_entradas": total,
        "pendientes": conteos.get("pendiente", 0),
        "en_revision": conteos.get("en_revision", 0),
        "aprobados": conteos.get("aprobado", 0),
        "en_produccion": conteos.get("en_produccion", 0),
        "publicados": publicados,
        "pospuestos": conteos.get("pospuesto", 0),
        "cancelados": conteos.get("cancelado", 0),
        "ajustados": cronograma.videos_ajustados,
        "porcentaje_completado": pct,
        "status_cronograma": cronograma.status,
    }


def _obtener_progreso(canal_id: str) -> dict:
    estado = channels.leer(canal_id)

    if not estado.cronograma_activo:
        return {
            "canal_id": canal_id,
            "tiene_cronograma": False,
        }

    cronograma = estado.cronograma_activo
    progreso = _calcular_progreso(cronograma)

    proxima = None
    for e in sorted(cronograma.entradas, key=lambda x: x.fecha_programada):
        if e.status in ("pendiente", "en_revision", "aprobado"):
            proxima = {
                "dia": e.dia,
                "fecha": e.fecha_programada,
                "titulo": e.titulo_sugerido,
                "status": e.status,
                "tipo": e.tipo_contenido,
            }
            break

    return {
        "canal_id": canal_id,
        "tiene_cronograma": True,
        "cronograma_id": cronograma.cronograma_id,
        "periodo": f"{cronograma.fecha_inicio} a {cronograma.fecha_fin}",
        "madurez_canal": cronograma.madurez_canal,
        "estrategia": cronograma.estrategia_secuencia,
        "progreso": progreso,
        "proxima_entrada": proxima,
        "entradas": [
            {
                "dia": e.dia,
                "fecha": e.fecha_programada,
                "titulo": e.titulo_sugerido,
                "tipo": e.tipo_contenido,
                "formato": e.formato,
                "prioridad": e.prioridad,
                "potencial_viral": e.potencial_viral,
                "status": e.status,
                "proyecto_id": e.proyecto_id,
                "titulo_final": e.titulo_final,
                "ajustes": len(e.ajustes_historial),
            }
            for e in cronograma.entradas
        ],
    }


# ── Modo EJECUTAR DIARIO (piloto automatico) ─────────────────

UMBRAL_REGENERACION = 3


def _ejecutar_diario(canal_id: str) -> dict:
    from shared.scheduler import esta_pausado

    if esta_pausado():
        log.info("ejecucion diaria omitida | canal=%s | razon=pausa_global", canal_id)
        return {
            "canal_id": canal_id,
            "accion": "omitido",
            "razon": "Pausa global activada",
        }

    estado = channels.leer(canal_id)
    modo = estado.modo_cronograma

    if modo == "manual":
        log.info("ejecucion diaria omitida | canal=%s | modo=manual", canal_id)
        return {
            "canal_id": canal_id,
            "accion": "omitido",
            "razon": "Modo manual — el usuario controla desde el UI",
            "modo": "manual",
        }

    if not estado.cronograma_activo:
        log.warning("ejecucion diaria | canal=%s | sin cronograma activo", canal_id)
        telegram.notificar_modo_sin_cronograma(estado.nombre)

        if modo == "auto":
            log.info("auto-generando cronograma | canal=%s", canal_id)
            try:
                result_gen = _generar_cronograma(canal_id, 30, 4, None)
                return {
                    "canal_id": canal_id,
                    "accion": "cronograma_auto_generado",
                    "modo": modo,
                    "cronograma_id": result_gen.get("cronograma_id"),
                    "total_videos": result_gen.get("total_videos"),
                }
            except Exception as exc:
                log.error("error auto-generando cronograma: %s", exc)
                return {
                    "canal_id": canal_id,
                    "accion": "error",
                    "razon": f"Error generando cronograma: {exc}",
                }

        return {
            "canal_id": canal_id,
            "accion": "sin_cronograma",
            "modo": modo,
            "razon": "Sin cronograma activo. Genera uno desde el Dashboard.",
        }

    cronograma = estado.cronograma_activo

    # ── Buscar la proxima entrada pendiente ──
    hoy = datetime.utcnow().strftime("%Y-%m-%d")
    entrada_hoy = None
    entrada_proxima = None

    for e in sorted(cronograma.entradas, key=lambda x: x.fecha_programada):
        if e.status not in ("pendiente", "en_revision"):
            continue
        if e.fecha_programada <= hoy and entrada_hoy is None:
            entrada_hoy = e
        if entrada_proxima is None:
            entrada_proxima = e

    entrada = entrada_hoy or entrada_proxima

    if not entrada:
        log.info("ejecucion diaria | canal=%s | sin entradas pendientes", canal_id)
        _verificar_regeneracion(canal_id, estado, cronograma, modo)
        return {
            "canal_id": canal_id,
            "accion": "sin_entradas_pendientes",
            "modo": modo,
            "razon": "No hay entradas pendientes en el cronograma",
        }

    log.info(
        "ejecucion diaria | canal=%s | modo=%s | dia=%d | titulo=%s",
        canal_id, modo, entrada.dia, entrada.titulo_sugerido,
    )

    # ── Revisar vigencia ──
    try:
        result_revision = _revisar_entrada(canal_id, entrada.dia)
        decision = result_revision.get("decision", "proceder")
        score = result_revision.get("score_vigencia", 5.0)
        titulo_final = result_revision.get("titulo_final", entrada.titulo_sugerido)
    except Exception as exc:
        log.error("error en revision de vigencia: %s", exc)
        decision = "proceder"
        score = None
        titulo_final = entrada.titulo_sugerido

    # ── Actuar segun el modo ──
    if modo == "semi_auto":
        estado_fresh = channels.leer(canal_id)
        entrada_fresh = None
        for e in estado_fresh.cronograma_activo.entradas:
            if e.dia == entrada.dia:
                entrada_fresh = e
                break

        telegram.notificar_video_hoy_semiauto(
            canal=estado.nombre,
            dia=entrada.dia,
            titulo=titulo_final,
            decision=decision,
            score=score,
            tipo_contenido=entrada_fresh.tipo_contenido if entrada_fresh else entrada.tipo_contenido,
            formato=entrada_fresh.formato if entrada_fresh else entrada.formato,
        )

        _verificar_regeneracion(canal_id, estado, cronograma, modo)

        return {
            "canal_id": canal_id,
            "accion": "revision_completada_esperando_ok",
            "modo": "semi_auto",
            "dia": entrada.dia,
            "titulo": titulo_final,
            "decision": decision,
            "score_vigencia": score,
            "razon": "Revision completada. Notificacion enviada. Esperando OK del usuario en el Dashboard.",
        }

    elif modo == "auto":
        estado_fresh = channels.leer(canal_id)
        cron_fresh = estado_fresh.cronograma_activo

        entrada_fresh = None
        for e in cron_fresh.entradas:
            if e.dia == entrada.dia:
                entrada_fresh = e
                break

        if not entrada_fresh or entrada_fresh.status != "aprobado":
            log.warning(
                "entrada dia %d no esta aprobada tras revision (status=%s)",
                entrada.dia, entrada_fresh.status if entrada_fresh else "?",
            )
            _verificar_regeneracion(canal_id, estado_fresh, cron_fresh, modo)
            return {
                "canal_id": canal_id,
                "accion": "entrada_no_aprobada",
                "dia": entrada.dia,
                "status": entrada_fresh.status if entrada_fresh else "?",
            }

        proyecto_id = f"auto_{canal_id[:8]}_{entrada.dia}_{datetime.utcnow().strftime('%Y%m%d')}"

        _gestionar_entrada(canal_id, entrada.dia, "en_produccion", {
            "proyecto_id": proyecto_id,
            "razon": "Iniciado por piloto automatico",
        })

        telegram.notificar_video_auto_iniciado(
            canal=estado.nombre,
            dia=entrada.dia,
            titulo=titulo_final,
            tipo_contenido=entrada_fresh.tipo_contenido,
        )

        _verificar_regeneracion(canal_id, estado_fresh, cron_fresh, modo)

        return {
            "canal_id": canal_id,
            "accion": "produccion_iniciada",
            "modo": "auto",
            "dia": entrada.dia,
            "titulo": titulo_final,
            "proyecto_id": proyecto_id,
            "decision_vigencia": decision,
            "score_vigencia": score,
        }

    return {"canal_id": canal_id, "accion": "modo_desconocido", "modo": modo}


def _verificar_regeneracion(canal_id: str, estado, cronograma, modo: str):
    pendientes = sum(
        1 for e in cronograma.entradas
        if e.status in ("pendiente", "en_revision", "aprobado")
    )

    if pendientes > UMBRAL_REGENERACION:
        return

    log.info(
        "cronograma casi agotado | canal=%s | pendientes=%d | umbral=%d",
        canal_id, pendientes, UMBRAL_REGENERACION,
    )

    telegram.notificar_cronograma_agotandose(
        canal=estado.nombre,
        entradas_restantes=pendientes,
        modo=modo,
    )

    if modo == "auto":
        log.info("auto-regenerando cronograma | canal=%s", canal_id)
        try:
            freq = cronograma.frecuencia_semanal or 4
            _generar_cronograma(canal_id, 30, freq, None)
            log.info("cronograma auto-regenerado | canal=%s", canal_id)
        except Exception as exc:
            log.error("error auto-regenerando cronograma: %s", exc)


# ── Logica principal (router de modos) ────────────────────────

def logica(request: AgenteRequest) -> dict:
    modo = request.parametros.get("modo", "generar")
    canal_id = request.parametros.get("canal_id", "")

    if not canal_id:
        raise ValueError("Falta 'canal_id' en parametros")

    if modo == "generar":
        periodo = request.parametros.get("periodo_dias", 30)
        frecuencia = request.parametros.get("frecuencia_semanal", 4)
        fecha_inicio = request.parametros.get("fecha_inicio")

        if periodo not in (7, 15, 20, 30):
            raise ValueError(
                f"periodo_dias debe ser 7, 15, 20 o 30 (recibido: {periodo})"
            )
        if not 1 <= frecuencia <= 7:
            raise ValueError(
                f"frecuencia_semanal debe estar entre 1 y 7 (recibido: {frecuencia})"
            )

        return _generar_cronograma(canal_id, periodo, frecuencia, fecha_inicio)

    elif modo == "revisar":
        dia = request.parametros.get("dia")
        if dia is None:
            raise ValueError(
                "Falta 'dia' en parametros (numero de entrada a revisar)"
            )
        return _revisar_entrada(canal_id, int(dia))

    elif modo == "adaptar":
        senal = request.parametros.get("senal")
        if not senal:
            raise ValueError(
                "Falta 'senal' en parametros (dict con tipo_senal, video_titulo, etc.)"
            )
        return _adaptar_cronograma(canal_id, senal)

    elif modo == "gestionar":
        dia = request.parametros.get("dia")
        nuevo_status = request.parametros.get("nuevo_status", "")
        if dia is None:
            raise ValueError("Falta 'dia' en parametros")
        if not nuevo_status:
            raise ValueError(
                "Falta 'nuevo_status' en parametros. "
                "Valores: en_produccion, publicado, pospuesto, cancelado"
            )
        datos = {
            "proyecto_id": request.parametros.get("proyecto_id"),
            "titulo_final": request.parametros.get("titulo_final"),
            "nueva_fecha": request.parametros.get("nueva_fecha"),
            "razon": request.parametros.get("razon", ""),
        }
        return _gestionar_entrada(canal_id, int(dia), nuevo_status, datos)

    elif modo == "progreso":
        return _obtener_progreso(canal_id)

    elif modo == "ejecutar_diario":
        return _ejecutar_diario(canal_id)

    elif modo == "set_modo":
        nuevo_modo = request.parametros.get("modo_cronograma", "")
        if nuevo_modo not in ("manual", "semi_auto", "auto"):
            raise ValueError(
                f"modo_cronograma debe ser 'manual', 'semi_auto' o 'auto' (recibido: '{nuevo_modo}')"
            )
        channels.actualizar(canal_id, modo_cronograma=nuevo_modo)
        log.info("modo cronograma cambiado | canal=%s | modo=%s", canal_id, nuevo_modo)
        return {
            "canal_id": canal_id,
            "modo_cronograma": nuevo_modo,
            "accion": "modo_actualizado",
        }

    else:
        raise ValueError(
            f"Modo desconocido: '{modo}'. "
            f"Validos: 'generar', 'revisar', 'adaptar', 'gestionar', 'progreso', "
            f"'ejecutar_diario', 'set_modo'"
        )


ejecutar = envolver_logica(AGENTE_ID, logica)


@app.post("/ejecutar", response_model=AgenteResponse)
def ejecutar_endpoint(request: AgenteRequest):
    return ejecutar(request)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=REGISTRO_AGENTES[AGENTE_ID])
