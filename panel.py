# ===========================================
# WPPMON V2 - PANEL MODULAR (PARTE 1)
# Arquitectura: panel.py + analyzer.py + detectors.py
# Diseño: C1 Hacker Pro + T2 + Cards B + Mobile Ready
# ===========================================

from flask import Flask, render_template, request, send_from_directory, jsonify, redirect, url_for
from markupsafe import Markup
import os
import json
from datetime import datetime, timedelta, timezone
from analyzer import (
    leer_log,
    generar_sesiones,
    obtener_resumen_dia,
    exportar_json_dia,
    obtener_json_dia, calcular_gaps_por_sesiones, sesiones_para_gaps
)
from detectors import (
    clasificar_gaps,
    detectar_charlas_avanzado,
    metricas_psicologicas
)

app = Flask(__name__)
JSON_DIAS_PATH = "json_dias"
if not os.path.exists(JSON_DIAS_PATH):
    os.makedirs(JSON_DIAS_PATH)
FALSOS_PATH = "falsos.json"

# Día abreviado en español para formatear fechas
DAY_LABELS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]

# -------------------------------------------
# Filtro Jinja para mostrar fechas con día
# -------------------------------------------
def _format_fecha_con_dia(valor, dia_texto=None, incluir_hora=True):
    if valor is None:
        return ""
    try:
        dt = datetime.fromisoformat(valor) if isinstance(valor, str) else valor
    except Exception:
        return valor

    dia = dia_texto if dia_texto else DAY_LABELS[dt.weekday()]
    fecha_fmt = dt.strftime("%Y-%m-%d")
    if incluir_hora:
        return f"{dia} {fecha_fmt} {dt.strftime('%H:%M:%S')}"
    return f"{dia} {fecha_fmt}"


@app.template_filter("fecha_dia")
def fecha_dia_filter(valor, dia_texto=None, incluir_hora=True):
    return _format_fecha_con_dia(valor, dia_texto, incluir_hora)


# -------------------------------------------
# Filtro: obtener rango de fechas desde query
# -------------------------------------------
def obtener_rango_fechas(req):
    hoy = datetime.now().date()

    # Si se envía date=YYYY-MM-DD, prioriza ese día
    date_str = req.args.get("date")
    if date_str:
        try:
            fecha = datetime.fromisoformat(date_str).date()
            return fecha, fecha, "dia"
        except Exception:
            pass

    filtro = req.args.get("filter", "hoy").lower()
    start_str = req.args.get("start")
    end_str = req.args.get("end")

    def parse_fecha(s):
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            return None

    if filtro == "ayer":
        start = end = hoy - timedelta(days=1)
    elif filtro in {"7", "15", "30"}:
        dias = int(filtro)
        start = hoy - timedelta(days=dias - 1)
        end = hoy
    elif filtro == "rango" or start_str or end_str:
        start = parse_fecha(start_str) or hoy
        end = parse_fecha(end_str) or start
        if end < start:
            start, end = end, start
        filtro = "rango"
    else:
        filtro = "hoy"
        start = end = hoy

    return start, end, filtro


# -------------------------------------------
# Últimos 5 días (anteriores al día actual)
# -------------------------------------------
def obtener_ultimos_5_dias_v0():
    hoy = datetime.now().date()
    dias = []
    for i in range(1, 6):
        d = hoy - timedelta(days=i)
        dias.append({
            "label": f"{DAY_LABELS[d.weekday()]} {d.day}",
            "date": d.isoformat()
        })
    return dias

# -------------------------------------------
# Ultimos 7 dias (anteriores al dia actual)
# -------------------------------------------
def obtener_ultimos_5_dias():
    hoy = datetime.now().date()
    return [
        {
            "label": f"{DAY_LABELS[d.weekday()]} {d.day}",
            "date": d.isoformat()
        }
        for d in (hoy - timedelta(days=i) for i in range(1, 8))
    ]

# -------------------------------------------
# Filtrar lista de eventos por rango de fechas
# eventos: iterable de (timestamp, ...)
# -------------------------------------------
def filtrar_eventos_por_fecha(eventos, start, end):
    if not eventos:
        return eventos
    return [
        ev for ev in eventos
        if start <= ev[0].date() <= end
    ]


# -------------------------------------------
# Filtrar sesiones por dia de inicio
# -------------------------------------------
def filtrar_sesiones_por_dia(sesiones, start, end):
    if not sesiones:
        return []
    return [
        s for s in sesiones
        if start <= (s.get("session_day") or s.get("inicio").date()) <= end
    ]

def _filtrar_restarts(eventos):
    """
    Oculta entradas marcadas como RESTART para no mostrarlas en vistas.
    """
    if not eventos:
        return []
    return [ev for ev in eventos if len(ev) < 4 or not ev[3]]

def _leer_log_panel():
    """
    Log listo para el panel (sin eventos RESTART).
    """
    return _filtrar_restarts(leer_log())


# -------------------------------------------
# Ordenar sesiones por duracion (desc)
# -------------------------------------------
def _ordenar_por_duracion_desc(lista):
    return sorted(lista, key=lambda x: x.get("duracion"), reverse=True)


# -------------------------------------------
# Obtener un dia objetivo unico para vistas basadas en session_day
# -------------------------------------------
def _obtener_dia_objetivo(req):
    start, end, filtro = obtener_rango_fechas(req)
    dia_param = req.args.get("dia") or req.args.get("date")
    target_day = start

    if dia_param:
        try:
            target_day = datetime.fromisoformat(dia_param).date()
            filtro = "dia"
        except Exception:
            target_day = start

    return target_day, filtro


# -------------------------------------------
# Filtro: duración en minutos u horas
# -------------------------------------------
@app.template_filter("duracion_min")
def duracion_min_filter(valor):
    if valor is None:
        return ""

    total_seconds = None

    # Timedelta
    if hasattr(valor, "total_seconds"):
        total_seconds = int(valor.total_seconds())
    elif isinstance(valor, str):
        # Intentar parsear "H:MM:SS" o "MM:SS"
        partes = valor.split(":")
        try:
            if len(partes) == 3:
                h, m, s = map(int, partes)
                total_seconds = h * 3600 + m * 60 + s
            elif len(partes) == 2:
                m, s = map(int, partes)
                total_seconds = m * 60 + s
        except ValueError:
            total_seconds = None

    if total_seconds is None:
        return valor

    if total_seconds < 60:
        return str(total_seconds)

    minutes = total_seconds // 60
    if total_seconds < 3600:
        return str(minutes)

    hours = minutes // 60
    rem_mins = minutes % 60
    return f"{hours}h {rem_mins:02d}"


# -------------------------------------------
# Filtro: reemplazar ceros iniciales por "_"
# en formato HH:MM:SS
# -------------------------------------------
@app.template_filter("zero_mask")
def zero_mask_filter(valor):
    if valor is None:
        return ""

    total_seconds = None

    if hasattr(valor, "total_seconds"):
        total_seconds = int(valor.total_seconds())
    elif isinstance(valor, str):
        partes = valor.split(":")
        try:
            if len(partes) == 3:
                h, m, s = map(int, partes)
                total_seconds = h * 3600 + m * 60 + s
            elif len(partes) == 2:
                m, s = map(int, partes)
                total_seconds = m * 60 + s
        except ValueError:
            total_seconds = None

    if total_seconds is None:
        return valor

    hours = total_seconds // 3600
    minutes = (total_seconds // 60) % 60
    seconds = total_seconds % 60

    partes = []
    if hours > 0:
        partes.append(f"{hours} h")
    if minutes > 0 or hours > 0:
        partes.append(f"{minutes} m")
    if seconds > 0 or (hours == 0 and minutes == 0):
        partes.append(f"{seconds} s")

    base = " ".join(partes) if partes else "0 s"
    # Alinear a la derecha para que segundos caigan en la misma columna
    formatted = base.rjust(16)
    return Markup(formatted.replace(" ", "&nbsp;"))


# -------------------------------------------
# Helpers: duraciones y colores reutilizables
# -------------------------------------------
def _parse_duration_seconds(valor):
    if valor is None:
        return None

    if hasattr(valor, "total_seconds"):
        return int(valor.total_seconds())

    if isinstance(valor, str):
        try:
            dias = 0
            tiempo = valor

            if "day" in valor:
                partes = valor.split(",", 1)
                if len(partes) == 2:
                    dias_txt, tiempo = partes
                    dias = int(dias_txt.split()[0])
                    tiempo = tiempo.strip()

            hms = tiempo.split(":")
            if len(hms) == 3:
                horas, minutos, segundos = map(float, hms)
            elif len(hms) == 2:
                horas = 0
                minutos, segundos = map(float, hms)
            else:
                return None

            total = int(dias * 86400 + horas * 3600 + minutos * 60 + segundos)
            return total
        except Exception:
            return None

    return None


def _duration_minutes(valor):
    segundos = _parse_duration_seconds(valor)
    if segundos is None:
        return None
    return segundos / 60


@app.template_filter("duracion_hm")
def duracion_hm_filter(valor):
    segundos = _parse_duration_seconds(valor)
    if segundos is None:
        return valor
    horas = segundos // 3600
    mins = (segundos // 60) % 60
    secs = segundos % 60

    partes = []
    if horas:
        partes.append(f"{horas} h")
    if mins:
        partes.append(f"{mins} m")
    if secs:
        partes.append(f"{secs} s")

    if not partes:
        return "0 s"

    return " ".join(partes)


def _charla_badge_class(duracion, inicio=None):
    minutos = _duration_minutes(duracion)
    if minutos is None:
        return ""

    umbral_larga = CONFIG.get("charla_larga_min", 20)
    umbral_muy_larga = CONFIG.get("charla_muy_larga_min", 45)
    umbral_intima = CONFIG.get("charla_intima_min", 60)

    hora = None
    if inicio is not None:
        try:
            hora = inicio.hour if not isinstance(inicio, str) else datetime.fromisoformat(inicio).hour
        except Exception:
            hora = None

    if minutos >= umbral_intima:
        return "badge badge-red"

    if minutos >= umbral_larga and hora is not None and (hora >= 22 or hora <= 3):
        return "badge badge-red"

    if minutos >= umbral_larga or minutos >= umbral_muy_larga:
        return "badge badge-yellow"

    return "badge badge-green"


def _ordenar_por_inicio_desc(lista):
    return sorted(lista, key=lambda x: x.get("inicio"), reverse=True)


def _ordenar_gaps_desc(gaps_dict):
    for key, items in gaps_dict.items():
        gaps_dict[key] = sorted(items, key=lambda g: g.get("inicio"), reverse=True)
    return gaps_dict


def _ordenar_charlas_desc(charlas_dict):
    for key, items in charlas_dict.items():
        charlas_dict[key] = sorted(items, key=lambda c: c.get("inicio"), reverse=True)
    return charlas_dict


def _parse_datetime(value):
    """
    Convierte strings ISO o datetime en datetime; devuelve None si no se puede.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _to_iso_string(value):
    """
    Devuelve el valor en string ISO si es datetime, o su representaci?n directa si ya es string.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _ensure_falsos_file():
    if not os.path.exists(FALSOS_PATH):
        with open(FALSOS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)


def cargar_falsos():
    """
    Carga intervalos dudosos desde falsos.json.
    """
    _ensure_falsos_file()
    try:
        with open(FALSOS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception as exc:
        print("No se pudo leer falsos.json:", exc)
    return []


def guardar_falsos(falsos):
    """
    Persiste la lista de intervalos dudosos en falsos.json.
    """
    try:
        with open(FALSOS_PATH, "w", encoding="utf-8") as f:
            json.dump(falsos or [], f, indent=4, ensure_ascii=False)
    except Exception as exc:
        print("No se pudo guardar falsos.json:", exc)


# Cache en memoria, se refresca en las rutas al escribir
# Cache en memoria, se refresca en las rutas al escribir
FALSOS = cargar_falsos()


def _refresh_falsos():
    global FALSOS
    FALSOS = cargar_falsos()
    return FALSOS


def es_dudoso(inicio, fin):
    """
    Devuelve True si existe un intervalo en falsos.json con inicio y fin iguales.
    """
    inicio_str = _to_iso_string(inicio)
    fin_str = _to_iso_string(fin)
    if inicio_str is None or fin_str is None:
        return False

    for f in FALSOS:
        if inicio_str == f.get("inicio") and fin_str == f.get("fin"):
            return True
    return False


def _marcar_bloques_falsos(bloques):
    """
    Agrega las claves 'dudoso' y 'falso' a cada bloque con inicio/fin (solo visual).
    """
    if not bloques:
        return bloques

    for b in bloques:
        inicio = b.get("inicio")
        fin = b.get("fin")
        marcado = es_dudoso(inicio, fin)
        b["dudoso"] = marcado
        b["falso"] = marcado  # compat visual previa
    return bloques


def _marcar_falsos_en_dict_listas(data_dict):
    """
    Marca dudosos en cada lista dentro de un dict (ej: gaps, charlas).
    """
    if not isinstance(data_dict, dict):
        return data_dict
    for _, lista in data_dict.items():
        _marcar_bloques_falsos(lista)
    return data_dict


def _clasificar_gap_color(minutos, config):
    if minutos is None:
        return "badge"
    if minutos >= config.get("gap_rojo_min", 45):
        return "badge badge-red"
    if minutos >= config.get("gap_sospechoso_min", 15):
        return "badge badge-yellow"
    return "badge badge-green"


def _calcular_gap_offline_actual(eventos, config):
    if not eventos:
        return None

    eventos_sorted = sorted(eventos, key=lambda x: x[0])
    offline_inicio = None
    ultimo_gap = None

    for ts, status, *_ in eventos_sorted:
        if status == "offline":
            # Siempre usamos el último offline visto para evitar gaps inflados por colgadas
            offline_inicio = ts
        elif status == "online" and offline_inicio is not None:
            duracion = ts - offline_inicio
            ultimo_gap = {
                "inicio": offline_inicio,
                "fin": ts,
                "duracion": duracion,
                "ongoing": False
            }
            offline_inicio = None

    if offline_inicio is not None:
        ahora = datetime.now()
        duracion = ahora - offline_inicio
        ultimo_gap = {
            "inicio": offline_inicio,
            "fin": ahora,
            "duracion": duracion,
            "ongoing": True
        }

    if ultimo_gap is None:
        return None

    minutos = _duration_minutes(ultimo_gap["duracion"])
    horas = int(minutos // 60) if minutos is not None else 0
    mins = int(minutos % 60) if minutos is not None else 0

    return {
        **ultimo_gap,
        "minutos": minutos,
        "horas": horas,
        "mins": mins,
        "color": _clasificar_gap_color(minutos, config)
    }


def _extraer_gaps_simples(eventos):
    """
    Gaps offline sin clasificar (>=1s) con inicio/fin/duracion.
    """
    if not eventos:
        return []

    eventos_sorted = sorted(eventos, key=lambda x: x[0])
    offline_inicio = None
    gaps = []

    for ts, status, *_ in eventos_sorted:
        if status == "offline":
            # Actualizamos siempre para tomar el último offline antes del próximo online
            offline_inicio = ts
        elif status == "online" and offline_inicio is not None:
            duracion = ts - offline_inicio
            if duracion.total_seconds() >= 1:
                gaps.append({
                    "inicio": offline_inicio,
                    "fin": ts,
                    "duracion": duracion
                })
            offline_inicio = None

    if offline_inicio is not None:
        fin = datetime.now()
        duracion = fin - offline_inicio
        if duracion.total_seconds() >= 1:
            gaps.append({
                "inicio": offline_inicio,
                "fin": fin,
                "duracion": duracion
            })

    return gaps


def _calcular_estado_actual_duracion(eventos, status_actual, config):
    if not eventos or status_actual not in {"online", "offline"}:
        return None

    eventos_sorted = sorted(eventos, key=lambda x: x[0])

    target_ts = None
    for ts, st, *_ in reversed(eventos_sorted):
        if st == status_actual:
            target_ts = ts
            break

    if target_ts is None:
        return None

    ahora = datetime.now()
    duracion = ahora - target_ts
    minutos = _duration_minutes(duracion)
    horas = int(minutos // 60) if minutos is not None else 0
    mins = int(minutos % 60) if minutos is not None else 0

    return {
        "status": status_actual,
        "inicio": target_ts,
        "duracion": duracion,
        "horas": horas,
        "mins": mins,
        "color": _clasificar_gap_color(minutos, config)
    }


def _ordenar_informe_diario(data):
    if not data:
        return data

    if "sesiones" in data:
        data["sesiones"] = _ordenar_por_inicio_desc(data.get("sesiones", []))
        _marcar_bloques_falsos(data["sesiones"])

    if "gaps" in data:
        gaps_data = data.get("gaps", {})
        if isinstance(gaps_data, dict):
            for key in ["sueno", "sospechosos", "rojos", "cita"]:
                gaps_data.setdefault(key, [])
            data["gaps"] = _ordenar_gaps_desc(gaps_data)
            _marcar_falsos_en_dict_listas(data["gaps"])

    if "charlas" in data:
        charlas_data = data.get("charlas", {})
        if isinstance(charlas_data, dict):
            for key in ["largas", "muy_largas", "intimas"]:
                charlas_data.setdefault(key, [])
            data["charlas"] = _ordenar_charlas_desc(charlas_data)
            _marcar_falsos_en_dict_listas(data["charlas"])

    return data

# ===========================================
# CARGAR CONFIGURACIÓN GLOBAL
# ===========================================

DEFAULT_CONFIG = {
    "gap_sueno_horas": 5,
    "gap_sospechoso_min": 15,
    "gap_rojo_min": 45,
    "gap_cita_min": 90,
    "charla_larga_min": 20,
    "charla_muy_larga_min": 45,
    "charla_intima_min": 60,
    "LIST_FONT_SIZE_PX": 18
}

CONFIG_PATH = "config.json"


print("Working directory:", os.getcwd())
print("Ruta real usada para leer CSV:",
      os.path.abspath("whatsapp_presence_log.csv"))


def cargar_config():
    if not os.path.exists(CONFIG_PATH):
        raise Exception("config.json no encontrado.")
    with open(CONFIG_PATH, "r") as f:
        data = json.load(f)

    for key, default_val in DEFAULT_CONFIG.items():
        data.setdefault(key, default_val)

    try:
        data["LIST_FONT_SIZE_PX"] = int(data.get("LIST_FONT_SIZE_PX", DEFAULT_CONFIG["LIST_FONT_SIZE_PX"]))
    except Exception:
        data["LIST_FONT_SIZE_PX"] = DEFAULT_CONFIG["LIST_FONT_SIZE_PX"]

    return data

def guardar_config(nueva_config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(nueva_config, f, indent=4)

CONFIG = cargar_config()


@app.context_processor
def inject_globals():
    font_size = CONFIG.get("LIST_FONT_SIZE_PX", DEFAULT_CONFIG["LIST_FONT_SIZE_PX"])
    return {
        "list_font_size_px": font_size,
        "list_font_class": "list-font",
        "charla_badge_class": _charla_badge_class
    }


# ===========================================
# FUNCIÓN ESTADO ACTUAL (ONLINE/OFFLINE)
# ===========================================

ESTADO_PATH = "estado_actual.json"

def obtener_estado_actual():
    if not os.path.exists(ESTADO_PATH):
        return {"status": "desconocido", "timestamp": "N/A"}

    with open(ESTADO_PATH, "r") as f:
        return json.load(f)


# ===========================================
# RUTA PRINCIPAL
# ===========================================

@app.route("/")
def index():

    estado = obtener_estado_actual()
    status = estado.get("status", "offline")
    timestamp = estado.get("timestamp", "N/A")

    log = _leer_log_panel()
    offline_gap = _calcular_gap_offline_actual(log, CONFIG)
    estado_duracion = _calcular_estado_actual_duracion(log, status, CONFIG)
    # Resumen del día actual (sesiones, gaps, charlas)
    resumen = obtener_resumen_dia(log, CONFIG)

    return render_template(
        "index.html",
        title="WppMon",
        estado=status,
        timestamp=timestamp,
        resumen=resumen,
        offline_gap=offline_gap,
        estado_duracion=estado_duracion
    )


# ===========================================
# RUTAS PRINCIPALES (PARTE 2)
# ===========================================

# -------------------------------------------
# Sesiones
# -------------------------------------------
@app.route("/sesiones")
def sesiones():

    target_day, filtro = _obtener_dia_objetivo(request)
    ultimos_dias = obtener_ultimos_5_dias()
    _refresh_falsos()

    log = _leer_log_panel()
    sesiones = generar_sesiones(log)
    sesiones = [
        s for s in sesiones
        if s.get("session_day") == target_day
    ]
    sesiones = _ordenar_por_inicio_desc(sesiones)
    _marcar_bloques_falsos(sesiones)

    return render_template(
        "sesiones.html",
        title="Sesiones",
        sesiones=sesiones,
        filtro_activo=filtro,
        start_date=target_day.isoformat(),
        end_date=target_day.isoformat(),
        ultimos_dias=ultimos_dias
    )


# -------------------------------------------
# Gaps (Sueño + Sospechosos + Cita)
# -------------------------------------------
@app.route("/gaps")
def gaps():

    target_day, filtro = _obtener_dia_objetivo(request)
    ultimos_dias = obtener_ultimos_5_dias()
    _refresh_falsos()

    log = _leer_log_panel()
    sesiones = generar_sesiones(log)
    sesiones_del_dia = [
        s for s in sesiones
        if s.get("session_day") == target_day
    ]
    sesiones_para_gap = sesiones_para_gaps(sesiones, target_day)

    gaps_clasificados = calcular_gaps_por_sesiones(sesiones_para_gap, CONFIG, target_day)
    gaps_clasificados = _ordenar_gaps_desc(gaps_clasificados)
    _marcar_falsos_en_dict_listas(gaps_clasificados)

    return render_template(
        "gaps.html",
        title="Gaps & Sueño",
        gaps=gaps_clasificados,
        filtro_activo=filtro,
        start_date=target_day.isoformat(),
        end_date=target_day.isoformat(),
        ultimos_dias=ultimos_dias
    )


# -------------------------------------------
# Timeline
# -------------------------------------------
@app.route("/timeline")
def timeline():

    target_day, filtro = _obtener_dia_objetivo(request)

    ultimos_dias = obtener_ultimos_5_dias()
    _refresh_falsos()

    log = _leer_log_panel()
    sesiones = generar_sesiones(log)
    sesiones = [
        s for s in sesiones
        if s.get("session_day") == target_day
    ]
    sesiones = _ordenar_por_duracion_desc(sesiones)
    _marcar_bloques_falsos(sesiones)

    return render_template(
        "timeline.html",
        title="Timeline",
        sesiones=sesiones,
        filtro_activo=filtro,
        start_date=target_day.isoformat(),
        end_date=target_day.isoformat(),
        ultimos_dias=ultimos_dias
    )


@app.route("/cronologico")
def cronologico():

    start, end, filtro = obtener_rango_fechas(request)
    ultimos_dias = obtener_ultimos_5_dias()
    _refresh_falsos()

    log = _leer_log_panel()
    sesiones = generar_sesiones(log)
    gaps_simples = _extraer_gaps_simples(log)

    items = []

    for s in sesiones or []:
        inicio = s.get("inicio")
        fin = s.get("fin")
        duracion = s.get("duracion")
        if inicio is not None:
            items.append({
                "tipo": "online",
                "inicio": inicio,
                "fin": fin,
                "duracion": duracion
            })

    for g in gaps_simples:
        items.append({
            "tipo": "offline",
            "inicio": g["inicio"],
            "fin": g["fin"],
            "duracion": g["duracion"]
        })

    if start and end:
        items = [
            it for it in items
            if it.get("inicio") and start <= it["inicio"].date() <= end
        ]

    items = sorted(items, key=lambda x: x["inicio"], reverse=True)
    _marcar_bloques_falsos(items)
    for it in items:
        it["inicio_str"] = _to_iso_string(it.get("inicio")) or ""
        it["fin_str"] = _to_iso_string(it.get("fin")) or ""

    return render_template(
        "cronologico.html",
        title="Cronologico",
        items=items,
        filtro_activo=filtro,
        start_date=start.isoformat() if start else "",
        end_date=end.isoformat() if end else "",
        ultimos_dias=ultimos_dias
    )


@app.route("/marcar_dudoso", methods=["POST"])
def marcar_dudoso():
    global FALSOS

    inicio = request.form.get("inicio")
    fin = request.form.get("fin")
    if not inicio or not fin:
        return redirect(url_for("cronologico"))

    FALSOS = cargar_falsos()
    if not es_dudoso(inicio, fin):
        FALSOS.append({
            "inicio": inicio,
            "fin": fin,
            "motivo": "Marcado manual"
        })
        guardar_falsos(FALSOS)
    return redirect(url_for("cronologico"))


@app.route("/desmarcar_dudoso", methods=["POST"])
def desmarcar_dudoso():
    global FALSOS

    inicio = request.form.get("inicio")
    fin = request.form.get("fin")
    if not inicio or not fin:
        return redirect(url_for("cronologico"))

    FALSOS = cargar_falsos()
    FALSOS = [f for f in FALSOS if not (inicio == f.get("inicio") and fin == f.get("fin"))]
    guardar_falsos(FALSOS)
    return redirect(url_for("cronologico"))


# -------------------------------------------
# Heatmap
# -------------------------------------------
@app.route("/heatmap")
def heatmap():

    start, end, filtro = obtener_rango_fechas(request)
    ultimos_dias = obtener_ultimos_5_dias()

    log = _leer_log_panel()
    log = filtrar_eventos_por_fecha(log, start, end)
    
    # Contar sesiones por hora
    horas = {h: 0 for h in range(24)}

    for ts, status, *_ in log:
        horas[ts.hour] += 1

    max_val = max(horas.values()) if horas else 1

    return render_template(
        "heatmap.html",
        title="Heatmap",
        horas=horas,
        max_val=max_val,
        filtro_activo=filtro,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        ultimos_dias=ultimos_dias
    )


# -------------------------------------------
# Charlas Sospechosas
# -------------------------------------------
@app.route("/sospechosas")
def sospechosas():

    target_day, filtro = _obtener_dia_objetivo(request)
    ultimos_dias = obtener_ultimos_5_dias()
    _refresh_falsos()

    log = _leer_log_panel()
    sesiones = generar_sesiones(log)
    sesiones = [
        s for s in sesiones
        if s.get("session_day") == target_day
    ]

    sospechosas = detectar_charlas_avanzado(sesiones, CONFIG)
    sospechosas = _ordenar_charlas_desc(sospechosas)
    _marcar_falsos_en_dict_listas(sospechosas)

    return render_template(
        "sospechosas.html",
        title="Charlas Sospechosas",
        sospechosas=sospechosas,
        filtro_activo=filtro,
        start_date=target_day.isoformat(),
        end_date=target_day.isoformat(),
        ultimos_dias=ultimos_dias
    )


# -------------------------------------------
# Métricas Psicológicas
# -------------------------------------------
@app.route("/metricas")
def metricas():

    target_day, filtro = _obtener_dia_objetivo(request)
    ultimos_dias = obtener_ultimos_5_dias()

    log = _leer_log_panel()
    sesiones = generar_sesiones(log)
    sesiones = [
        s for s in sesiones
        if s.get("session_day") == target_day
    ]

    metricas = metricas_psicologicas(sesiones, CONFIG)

    return render_template(
        "metricas.html",
        title="Metricas Psicologicas",
        metricas=metricas,
        filtro_activo=filtro,
        start_date=target_day.isoformat(),
        end_date=target_day.isoformat(),
        ultimos_dias=ultimos_dias
    )


@app.route("/dia")
def informe_dia():

    target_day, filtro = _obtener_dia_objetivo(request)
    _refresh_falsos()

    # Para "hoy" usamos TZ AR (-03) y rango completo del dia
    if filtro == "hoy":
        now_ar = datetime.now(timezone(timedelta(hours=-3)))
        target_day = now_ar.date()

    ultimos_dias = obtener_ultimos_5_dias()

    # Fecha objetivo (un solo dia) para el informe
    fecha_obj = target_day
    fecha_str = fecha_obj.isoformat()

    # Regenerar el JSON del dia justo antes de leerlo para no perder sesiones tardias
    exportar_json_dia(fecha_obj, CONFIG)
    data = obtener_json_dia(fecha_str)

    error = None
    if data is None:
        error = f"No hay informe para {fecha_str}"
    else:
        data = _ordenar_informe_diario(data)

    return render_template(
        "dia.html",
        title=f"Informe {fecha_str}",
        data=data,
        error=error,
        filtro_activo=filtro,
        start_date=fecha_obj.isoformat(),
        end_date=fecha_obj.isoformat(),
        ultimos_dias=ultimos_dias,
        fecha_actual=fecha_str
    )


@app.route("/ultimo-dia")
def ultimo_dia():

    log = _leer_log_panel()
    if not log:
        return "Sin datos."

    ultima_fecha = log[-1][0].date()
    dia_anterior = ultima_fecha - timedelta(days=1)

    return informe_dia_real(str(dia_anterior))



def informe_dia_real(fecha):
    """Función interna usada por ultimo-dia"""
    _refresh_falsos()
    data = obtener_json_dia(fecha)
    if data is None:
        return f"No JSON para {fecha}"
    data = _ordenar_informe_diario(data)
    return render_template(
        "dia.html",
        title=f"Informe {fecha}",
        data=data
    )



# -------------------------------------------
# Descargar JSON de un día
# /descargar-json?fecha=2025-11-25
# -------------------------------------------
@app.route("/descargar-json")
def descargar_json():

    fecha = request.args.get("fecha")
    if not fecha:
        return "Falta ?fecha="

    filename = f"{fecha}.json"
    fullpath = os.path.join(JSON_DIAS_PATH, filename)

    if not os.path.exists(fullpath):
        return f"No existe JSON para {fecha}"

    return send_from_directory(JSON_DIAS_PATH, filename, as_attachment=True)



# -------------------------------------------
# Generación automática de JSON por día
# Se ejecuta cada vez que accedemos a / o /sesiones etc.
# -------------------------------------------

@app.before_request
def generar_json_diario_automatico():
    """
    Cada request verifica:
    - Última fecha con datos
    - Si el JSON del día no existe → lo genera
    """

    log = _leer_log_panel()
    if not log:
        return

    # fecha del último registro
    fecha = log[-1][0].date()

    # path JSON
    json_file = os.path.join(JSON_DIAS_PATH, f"{fecha.isoformat()}.json")

    if not os.path.exists(json_file):
        # generar JSON del día
        exportar_json_dia(fecha, CONFIG)



# ===========================================
# CONFIGURACIÓN (PARTE 4 - FINAL)
# ===========================================

# -------------------------------------------
# Página de configuración
# -------------------------------------------
@app.route("/config")
def config_page():
    return render_template(
        "config.html",
        title="Configuración",
        config=CONFIG
    )


# -------------------------------------------
# Guardar configuración
# -------------------------------------------
@app.route("/config-save", methods=["POST"])
def config_save():

    global CONFIG

    nueva = {
        "gap_sueno_horas": float(request.form.get("gap_sueno_horas", CONFIG["gap_sueno_horas"])),
        "gap_sospechoso_min": int(request.form.get("gap_sospechoso_min", CONFIG["gap_sospechoso_min"])),
        "gap_rojo_min": int(request.form.get("gap_rojo_min", CONFIG["gap_rojo_min"])),
        "gap_cita_min": int(request.form.get("gap_cita_min", CONFIG["gap_cita_min"])),
        "charla_larga_min": int(request.form.get("charla_larga_min", CONFIG["charla_larga_min"])),
        "charla_muy_larga_min": int(request.form.get("charla_muy_larga_min", CONFIG["charla_muy_larga_min"])),
        "charla_intima_min": int(request.form.get("charla_intima_min", CONFIG["charla_intima_min"])),
        "LIST_FONT_SIZE_PX": int(request.form.get("LIST_FONT_SIZE_PX", CONFIG.get("LIST_FONT_SIZE_PX", DEFAULT_CONFIG["LIST_FONT_SIZE_PX"])))
    }

    # Guardar en archivo
    guardar_config(nueva)

    # Recargar en memoria

    CONFIG = cargar_config()

    return render_template(
        "config.html",
        title="Configuración",
        config=CONFIG,
        msg="Guardado correctamente."
    )



# ===========================================
# INICIAR SERVIDOR
# ===========================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



