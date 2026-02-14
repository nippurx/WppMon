# ===========================================
# ANALYZER.PY - Procesamiento base del log
# ===========================================

import os
import json
import csv
from datetime import datetime, timedelta
from detectors import (
    clasificar_gaps,
    detectar_charlas_avanzado,
    metricas_psicologicas
)


LOG_PATH = "whatsapp_presence_log.csv"
JSON_DIAS_PATH = "json_dias"
os.makedirs(JSON_DIAS_PATH, exist_ok=True)

# Mapear abreviaturas de dias en espanol
DIAS_MAP = {
    "lun": 0,
    "mar": 1,
    "mie": 2,
    "jue": 3,
    "vie": 4,
    "sab": 5,
    "dom": 6
}

DAY_LABELS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]


# -------------------------------------------
# Leer el log CSV
# -------------------------------------------
def leer_log():

    if not os.path.exists(LOG_PATH):
        return []

    eventos = []

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # header

        for row in reader:
            try:
                raw = row[0].strip()
                status = row[1].strip().lower()

                # Formato esperado: "dom 2025-11-23 12:01:47"
                partes = raw.split(" ", 1)

                if len(partes) == 2 and partes[0].lower() in DIAS_MAP:
                    dia_texto = partes[0].lower()
                    fecha_hora = partes[1]
                else:
                    # Sin dia al inicio
                    dia_texto = None
                    fecha_hora = raw

                # Parsear fecha real
                timestamp = datetime.fromisoformat(fecha_hora)

                eventos.append((timestamp, status, dia_texto))

            except Exception:
                continue

    eventos.sort(key=lambda x: x[0])
    return eventos


# -------------------------------------------
# Generar sesiones (online segmentado)
# -------------------------------------------
def generar_sesiones(eventos):

    sesiones = []
    inicio = None
    inicio_dia = None

    for ts, estado, dia_texto in eventos:

        if estado == "online":
            if inicio is None:
                inicio = ts
                inicio_dia = dia_texto

        elif estado == "offline":
            if inicio is not None:
                session_day = inicio.date()
                session_day_name = DAY_LABELS[inicio.weekday()]
                sesiones.append({
                    "inicio": inicio,
                    "inicio_dia": inicio_dia or session_day_name,
                    "fin": ts,
                    "fin_dia": dia_texto or DAY_LABELS[ts.weekday()],
                    "duracion": ts - inicio,
                    "session_day": session_day,
                    "session_day_name": session_day_name
                })
                inicio = None
                inicio_dia = None

    return sesiones


# -------------------------------------------
# Agrupar sesiones por fecha
# -------------------------------------------
def sesiones_por_dia(sesiones):

    dias = {}

    for s in sesiones:
        fecha = s.get("session_day") or s["inicio"].date()
        if fecha not in dias:
            dias[fecha] = []
        dias[fecha].append(s)

    return dias


# -------------------------------------------
# Construir lista de sesiones para gaps (incluye primera del día siguiente)
# -------------------------------------------
def sesiones_para_gaps(sesiones, target_day):
    if not sesiones:
        return []

    sesiones_dia = [s for s in sesiones if s.get("session_day") == target_day]
    if not sesiones_dia:
        return []

    sesiones_sorted = sorted(sesiones, key=lambda x: x["inicio"])
    ultima_sesion_dia = max(sesiones_dia, key=lambda x: x["inicio"])

    # Buscar la primera sesión después de la última del día
    siguiente = None
    for s in sesiones_sorted:
        if s["inicio"] > ultima_sesion_dia["fin"]:
            siguiente = s
            break

    if siguiente:
        return sorted(sesiones_dia + [siguiente], key=lambda x: x["inicio"])
    return sorted(sesiones_dia, key=lambda x: x["inicio"])


# -------------------------------------------
# Calcular gaps a partir de sesiones ordenadas
# Gap pertenece al día de inicio de la sesión siguiente
# -------------------------------------------
def calcular_gaps_por_sesiones(sesiones, config, target_day=None):
    if not sesiones:
        return {
            "sueno": [],
            "sospechosos": [],
            "rojos": [],
            "cita": []
        }

    if config is None:
        gap_sueno_horas = 5
        gap_sosp = 15
        gap_rojo = 45
        gap_cita = 90
    else:
        gap_sueno_horas = config.get("gap_sueno_horas", 5)
        gap_sosp = config.get("gap_sospechoso_min", 15)
        gap_rojo = config.get("gap_rojo_min", 45)
        gap_cita = config.get("gap_cita_min", 90)

    gaps = {
        "sueno": [],
        "sospechosos": [],
        "rojos": [],
        "cita": []
    }

    sesiones_ordenadas = sorted(
        [s for s in sesiones if s.get("fin")],
        key=lambda x: x["inicio"]
    )

    for prev, curr in zip(sesiones_ordenadas, sesiones_ordenadas[1:]):
        delta = curr["inicio"] - prev["fin"]
        if delta.total_seconds() <= 0:
            continue

        minutos = delta.total_seconds() / 60.0
        gap_day = target_day if target_day else curr.get("session_day")
        gap_day_name = DAY_LABELS[gap_day.weekday()] if gap_day else curr.get("session_day_name")

        gap_data = {
            "inicio": prev["fin"],
            "fin": curr["inicio"],
            "duracion": delta,
            "session_day": gap_day,
            "session_day_name": gap_day_name
        }

        if minutos >= gap_sueno_horas * 60:
            gaps["sueno"].append(gap_data)

        elif minutos >= gap_sosp:
            gaps["sospechosos"].append(gap_data)

        if minutos >= gap_rojo:
            gaps["rojos"].append(gap_data)

        if minutos >= gap_cita:
            gaps["cita"].append(gap_data)

    return gaps


# -------------------------------------------
# Contar gaps sospechosos a partir de sesiones del dia
# -------------------------------------------
def _contar_gaps_sospechosos(sesiones, config, target_day):
    if not sesiones:
        return 0

    sesiones_ext = sesiones_para_gaps(sesiones, target_day)
    gaps = calcular_gaps_por_sesiones(sesiones_ext, config, target_day)
    return len(gaps.get("sospechosos", []))


# -------------------------------------------
# Resumen simple para index
# -------------------------------------------
def obtener_resumen_dia(eventos=None, config=None):

    if eventos is None:
        eventos = leer_log()
    sesiones = generar_sesiones(eventos)

    hoy = datetime.now().date()

    sesiones_del_dia = [s for s in sesiones if s.get("session_day") == hoy]
    charlas = detectar_charlas_avanzado(sesiones_del_dia, config)
    gaps_sospechosos = _contar_gaps_sospechosos(sesiones_del_dia, config, hoy)

    return {
        "sesiones_hoy": len(sesiones_del_dia),
        "gaps_sos": gaps_sospechosos,
        "charlas_largas": len(charlas["largas"])
    }


# -------------------------------------------
# Exportar JSON de un dia
# -------------------------------------------
def exportar_json_dia(fecha, config):

    # Normalizar la fecha a datetime.date para evitar errores con strings
    if isinstance(fecha, str):
        fecha_dt = datetime.fromisoformat(fecha).date()
    elif isinstance(fecha, datetime):
        fecha_dt = fecha.date()
    else:
        fecha_dt = fecha

    eventos = leer_log()

    # 1) Filtrar solo eventos del dia (para gaps)
    eventos_dia = [
        (ts, st, dia_txt)
        for ts, st, dia_txt in eventos
        if ts.date() == fecha_dt
    ]

    # 2) Generar sesiones completas y quedarnos con las que inician en la fecha dada
    sesiones_completas = generar_sesiones(eventos)
    sesiones_objetivo = [
        s for s in sesiones_completas
        if s.get("session_day") == fecha_dt
    ]
    sesiones_para_gap = sesiones_para_gaps(sesiones_completas, fecha_dt)

    # 3) Calcular gaps + charlas + metricas
    gaps = calcular_gaps_por_sesiones(sesiones_para_gap, config, fecha_dt)

    sesiones_dt = []
    sesiones_json = []

    for s in sesiones_objetivo:
        si = s["inicio"]
        sf = s["fin"]
        dur = s["duracion"]
        session_day = s.get("session_day")

        sesiones_dt.append({
            "inicio": si,
            "fin": sf,
            "duracion": dur
        })

        sesiones_json.append({
            "inicio": si.isoformat(),
            "inicio_dia": s.get("inicio_dia"),
            "fin": sf.isoformat(),
            "fin_dia": s.get("fin_dia"),
            "duracion": str(dur),
            "session_day": session_day.isoformat() if session_day else None,
            "session_day_name": s.get("session_day_name")
        })

    charlas = detectar_charlas_avanzado(sesiones_dt, config)
    metricas = metricas_psicologicas(sesiones_dt, config)

    # Adaptar gaps a JSON
    gaps_json = {}
    for key, items in gaps.items():
        gaps_json[key] = [
            {
                "inicio": g["inicio"].isoformat(),
                "fin": g["fin"].isoformat(),
                "duracion": str(g["duracion"]),
                "session_day": g.get("session_day").isoformat() if g.get("session_day") else None,
                "session_day_name": g.get("session_day_name")
            }
            for g in items
        ]

    # 4) Construir JSON final
    data = {
        "fecha": fecha_dt.isoformat(),
        "resumen": {
            "total_online": str(sum([s["duracion"] for s in sesiones_dt], timedelta())),
            "sesiones": len(sesiones_objetivo)
        },
        "sesiones": sesiones_json,
        "gaps": gaps_json,
        "charlas": {
            "largas": [
                {
                    "inicio": c["inicio"].isoformat(),
                    "fin": c["fin"].isoformat(),
                    "duracion": str(c["duracion"])
                }
                for c in charlas["largas"]
            ],
            "muy_largas": [
                {
                    "inicio": c["inicio"].isoformat(),
                    "fin": c["fin"].isoformat(),
                    "duracion": str(c["duracion"])
                }
                for c in charlas["muy_largas"]
            ],
            "intimas": [
                {
                    "inicio": c["inicio"].isoformat(),
                    "fin": c["fin"].isoformat(),
                    "duracion": str(c["duracion"])
                }
                for c in charlas["intimas"]
            ]
        },
        "metricas": metricas
    }

    # 5) Guardar JSON
    out_path = os.path.join(JSON_DIAS_PATH, f"{fecha_dt.isoformat()}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# -------------------------------------------
# Obtener JSON diario ya guardado
# -------------------------------------------
def obtener_json_dia(fecha_str):

    path = os.path.join(JSON_DIAS_PATH, f"{fecha_str}.json")

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

