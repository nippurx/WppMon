# ===========================================
# DETECTORS.PY
# Lógica avanzada de análisis del comportamiento digital
# ===========================================

from datetime import datetime, timedelta


# -------------------------------------------
# Helper: duración en minutos
# -------------------------------------------
def mins(td):
    return td.total_seconds() / 60.0


# ===========================================
# CLASIFICACIÓN DE GAPS
# ===========================================

def clasificar_gaps(eventos, config):

    if not eventos:
        return {
            "sueno": [],
            "sospechosos": [],
            "rojos": [],
            "cita": []
        }

    if config is None:
        # valores default por si falta config
        gap_sueno_horas = 5
        gap_sosp = 15
        gap_rojo = 45
        gap_cita = 90
    else:
        gap_sueno_horas = config["gap_sueno_horas"]
        gap_sosp = config["gap_sospechoso_min"]
        gap_rojo = config["gap_rojo_min"]
        gap_cita = config["gap_cita_min"]

    gaps = {
        "sueno": [],
        "sospechosos": [],
        "rojos": [],
        "cita": []
    }

    # detectar offline
    eventos_sorted = sorted(eventos, key=lambda x: x[0])

    offline_start = None

    for evento in eventos_sorted:
        if len(evento) < 2:
            continue

        ts, status = evento[0], evento[1]

        if status == "offline":
            if offline_start is None:
                offline_start = ts

        if status == "online":
            if offline_start is not None:
                dur = ts - offline_start
                minutos = mins(dur)

                # SUEÑO
                if minutos >= gap_sueno_horas * 60:
                    gaps["sueno"].append({
                        "inicio": offline_start.isoformat(),
                        "fin": ts.isoformat(),
                        "duracion": str(dur)
                    })

                # SOSPECHOSO 15+
                elif minutos >= gap_sosp:
                    gaps["sospechosos"].append({
                        "inicio": offline_start.isoformat(),
                        "fin": ts.isoformat(),
                        "duracion": str(dur)
                    })

                # ROJO 45+
                if minutos >= gap_rojo:
                    gaps["rojos"].append({
                        "inicio": offline_start.isoformat(),
                        "fin": ts.isoformat(),
                        "duracion": str(dur)
                    })

                # CITA 90+
                if minutos >= gap_cita:
                    gaps["cita"].append({
                        "inicio": offline_start.isoformat(),
                        "fin": ts.isoformat(),
                        "duracion": str(dur)
                    })

                offline_start = None

    return gaps



# ===========================================
# DETECCIÓN DE CHARLAS LARGAS
# ===========================================

def detectar_charlas_avanzado(sesiones, config):

    if config is None:
        charla_larga = 20
        charla_muy_larga = 45
        charla_intima = 60
    else:
        charla_larga = config["charla_larga_min"]
        charla_muy_larga = config["charla_muy_larga_min"]
        charla_intima = config["charla_intima_min"]

    resultado = {
        "largas": [],
        "muy_largas": [],
        "intimas": [],
        "sospechosas": []
    }

    for s in sesiones:
        if not s["fin"]:
            continue

        dur = mins(s["duracion"])

        # Charlas largas
        if dur >= charla_larga:
            resultado["largas"].append(s)

        # Muy largas
        if dur >= charla_muy_larga:
            resultado["muy_largas"].append(s)

        # Íntimas (>60 min)
        if dur >= charla_intima:
            resultado["intimas"].append(s)

        # Sospechosa: larga + en horario íntimo
        hora = s["inicio"].hour
        if dur >= charla_larga and (22 <= hora or hora <= 3):
            resultado["sospechosas"].append(s)

    return resultado



# ===========================================
# MÉTRICAS PSICOESTADÍSTICAS REALES
# (Riesgo de Tercero mejorado)
# ===========================================

from datetime import datetime

def metricas_psicologicas(sesiones, config, contexto=None):
    """
    sesiones: lista de sesiones del día (inicio, fin, duracion)
    config: thresholds del panel
    contexto: diccionario opcional con información emocional
        {
            "pelea_reciente": True/False,
            "distancia_emocional": True/False,
            "ventana_posible_tercero": True/False
        }
    """

    if not sesiones:
        return {
            "intensidad": 0,
            "sincronia": 0,
            "variacion": 0,
            "riesgo_tercero": "bajo",
            "riesgo_puntos": 0
        }

    # ---------------------------------------
    # Helpers internos
    # ---------------------------------------
    def minutos(td):
        return td.total_seconds() / 60.0

    def peso_horario(dt):
        h = dt.hour
        if 8 <= h <= 21:
            return 0
        if 21 < h <= 23:
            return 1
        if 23 < h <= 1:  # técnicamente cruza medianoche
            return 2
        if 1 < h <= 3:
            return 3
        if 3 < h <= 6:
            return 4
        return 0

    # ---------------------------------------
    # 1) Características de sesiones
    # ---------------------------------------
    total_min = sum(minutos(s["duracion"]) for s in sesiones)

    # Charlas largas (usamos config)
    larga = config.get("charla_larga_min", 20)
    muy_larga = config.get("charla_muy_larga_min", 45)
    intima = config.get("charla_intima_min", 60)

    charlas_largas = [s for s in sesiones if minutos(s["duracion"]) >= larga]
    charlas_muy_largas = [s for s in sesiones if minutos(s["duracion"]) >= muy_larga]
    charlas_intimas = [s for s in sesiones if minutos(s["duracion"]) >= intima]

    # ---------------------------------------
    # 2) Puntuación “riesgo real”
    # ---------------------------------------
    puntos = 0

    # Charlas
    puntos += min(len(charlas_largas) * 10, 30)
    puntos += min(len(charlas_muy_largas) * 20, 40)
    puntos += min(len(charlas_intimas) * 30, 60)

    # Horario de charlas
    for s in sesiones:
        puntos += peso_horario(s["inicio"])

    # ---------------------------------------
    # 3) Gaps (parte del análisis histórico)
    # ---------------------------------------
    # Detectamos sesiones ordenadas para medir gaps manualmente
    sesiones_sorted = sorted(sesiones, key=lambda x: x["inicio"])
    gaps45 = 0
    gaps90 = 0
    gaps180 = 0

    for prev, curr in zip(sesiones_sorted, sesiones_sorted[1:]):
        gap = curr["inicio"] - prev["fin"]
        gm = minutos(gap)
        if gm >= 180:
            gaps180 += 1
        elif gm >= 90:
            gaps90 += 1
        elif gm >= 45:
            gaps45 += 1

    puntos += gaps45 * 8
    puntos += gaps90 * 15
    puntos += gaps180 * 25

    # Actividad nocturna (23–03)
    nocturnas = [
        s for s in sesiones_sorted
        if 23 <= s["inicio"].hour or s["inicio"].hour <= 3
    ]
    puntos += len(nocturnas) * 5

    # ---------------------------------------
    # 4) CONTEXTO EMOCIONAL (opcional)
    # ---------------------------------------
    if contexto:
        if contexto.get("pelea_reciente"):
            puntos += 10
        if contexto.get("distancia_emocional"):
            puntos += 15
        if contexto.get("ventana_posible_tercero"):
            puntos += 20

    # ---------------------------------------
    # 5) Normalización (0–100)
    # ---------------------------------------
    puntos = max(0, min(100, puntos))

    # ---------------------------------------
    # 6) Etiqueta cualitativa
    # ---------------------------------------
    if puntos <= 20:
        riesgo = "bajo"
    elif puntos <= 40:
        riesgo = "medio"
    elif puntos <= 70:
        riesgo = "alto"
    else:
        riesgo = "critico"

    # Intensidad / sincronia / variacion (los mantenemos)
    horas = [s["inicio"].hour for s in sesiones_sorted]
    sincronia = min(100, sum(1 for h in horas if 8 <= h <= 23) * 8)
    variacion = min(100, len(set(horas)) * 10)
    intensidad = min(100, int(total_min * 1.2))

    return {
        "intensidad": intensidad,
        "sincronia": sincronia,
        "variacion": variacion,
        "riesgo_tercero": riesgo,
        "riesgo_puntos": puntos
    }


# ===========================================
# MÉTRICAS PSICOLÓGICAS ESTADÍSTICAS
# (NO inferencia emocional humana)
# ===========================================

def metricas_psicologicas_v0(sesiones, config):

    if not sesiones:
        return {
            "intensidad": 0,
            "sincronia": 0,
            "variacion": 0,
            "riesgo_tercero": "bajo"
        }

    # Intensidad emocional ≈ cantidad + duración
    total_min = sum([
        mins(s["duracion"]) for s in sesiones
        if s["duracion"].total_seconds() > 0
    ])

    intensidad = min(100, int(total_min * 1.2))

    # Sincronía = más sesiones en horario humano (8–1)
    sincronia = 0
    for s in sesiones:
        h = s["inicio"].hour
        if 8 <= h <= 23:
            sincronia += 1
    sincronia = min(100, sincronia * 8)

    # Variación = dispersión de horarios
    horas = [s["inicio"].hour for s in sesiones]
    variacion = len(set(horas)) * 10
    variacion = min(100, variacion)

    # Riesgo de tercero (estadístico)
    riesgo = "bajo"
    if total_min > 40:
        riesgo = "medio"
    if total_min > 70:
        riesgo = "alto"
    if total_min > 90:
        riesgo = "critico"

    return {
        "intensidad": intensidad,
        "sincronia": sincronia,
        "variacion": variacion,
        "riesgo_tercero": riesgo
    }
