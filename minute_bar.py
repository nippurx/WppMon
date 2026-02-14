from datetime import datetime, timedelta
import sys

from flask import render_template, request


MINUTES_PER_DAY = 1440


def _resolve_panel_module():
    panel_mod = sys.modules.get("panel")
    if panel_mod and hasattr(panel_mod, "obtener_rango_fechas"):
        return panel_mod

    main_mod = sys.modules.get("__main__")
    if main_mod and hasattr(main_mod, "obtener_rango_fechas"):
        return main_mod

    raise RuntimeError("No se pudo resolver el modulo panel con helpers de filtros.")


def _minute_index(dt):
    return dt.hour * 60 + dt.minute


def _empty_day_buckets(day_date):
    day_start = datetime.combine(day_date, datetime.min.time())
    buckets = []
    for i in range(MINUTES_PER_DAY):
        minute_start = day_start + timedelta(minutes=i)
        buckets.append(
            {
                "online_seconds": 0,
                "offline_seconds": 0,
                "transitions": 0,
                "label": minute_start.strftime("%H:%M"),
                "timestamp_inicio_minuto": minute_start,
                "timestamp_fin_minuto": minute_start + timedelta(minutes=1),
            }
        )
    return buckets


def _build_minute_map(eventos, start_date, end_date):
    if not start_date or not end_date or start_date > end_date:
        return []

    global_start = datetime.combine(start_date, datetime.min.time())
    global_end = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    day_map = {}
    day = start_date
    while day <= end_date:
        day_map[day] = _empty_day_buckets(day)
        day += timedelta(days=1)

    if not eventos:
        return _finalize_minute_map(day_map)

    eventos = sorted(eventos, key=lambda e: e[0])
    n = len(eventos)

    prev_idx = -1
    i = 0
    while i < n and eventos[i][0] < global_start:
        prev_idx = i
        i += 1

    current_status = eventos[prev_idx][1] if prev_idx >= 0 else None
    current_ts = global_start

    if current_status is None and i < n and eventos[i][0] < global_end:
        current_ts = max(global_start, eventos[i][0])
        current_status = eventos[i][1]
        i += 1

    while current_status is not None and current_ts < global_end:
        next_ts = eventos[i][0] if i < n else global_end
        if next_ts > global_end:
            next_ts = global_end

        if next_ts > current_ts:
            _accumulate_interval(day_map, current_ts, next_ts, current_status)

        if i >= n or next_ts >= global_end:
            break

        current_ts = next_ts
        current_status = eventos[i][1]
        i += 1

    for j in range(1, n):
        prev_status = eventos[j - 1][1]
        ts = eventos[j][0]
        status = eventos[j][1]

        if status == prev_status:
            continue
        if ts < global_start or ts >= global_end:
            continue

        d = ts.date()
        bucket = day_map.get(d)
        if bucket is None:
            continue
        bucket[_minute_index(ts)]["transitions"] += 1

    return _finalize_minute_map(day_map)


def _accumulate_interval(day_map, start_ts, end_ts, status):
    if status not in {"online", "offline"}:
        return

    cur = start_ts
    while cur < end_ts:
        minute_start = cur.replace(second=0, microsecond=0)
        minute_end = minute_start + timedelta(minutes=1)
        seg_end = minute_end if minute_end < end_ts else end_ts
        seconds = int((seg_end - cur).total_seconds())
        if seconds <= 0:
            break

        buckets = day_map.get(minute_start.date())
        if buckets is not None:
            idx = _minute_index(minute_start)
            if status == "online":
                buckets[idx]["online_seconds"] += seconds
            else:
                buckets[idx]["offline_seconds"] += seconds

        cur = seg_end


def _finalize_minute_map(day_map):
    panel_mod = _resolve_panel_module()
    day_labels = getattr(panel_mod, "DAY_LABELS", ["lun", "mar", "mie", "jue", "vie", "sab", "dom"])
    ordered_days = sorted(day_map.keys())
    output = []

    for day in ordered_days:
        buckets = day_map[day]
        total_online = 0
        total_offline = 0
        total_transitions = 0
        mix_count = 0

        for b in buckets:
            online_s = b["online_seconds"]
            offline_s = b["offline_seconds"]
            transitions = b["transitions"]
            total_online += online_s
            total_offline += offline_s
            total_transitions += transitions

            if online_s == 60 and offline_s == 0:
                color = "online"
            elif offline_s == 60 and online_s == 0:
                color = "offline"
            else:
                color = "mix"
                mix_count += 1

            b["color"] = color

        output.append(
            {
                "date": day.isoformat(),
                "day_label": f"{day_labels[day.weekday()]} {day.isoformat()}",
                "buckets": buckets,
                "total_online_seconds": total_online,
                "total_offline_seconds": total_offline,
                "mix_minutes": mix_count,
                "total_transitions": total_transitions,
            }
        )

    return output


def register_minute_bar(app):
    @app.route("/barra-minuto")
    def barra_minuto():
        panel_mod = _resolve_panel_module()
        start, end, filtro = panel_mod.obtener_rango_fechas(request)
        ultimos_dias = panel_mod.obtener_ultimos_5_dias()

        log = panel_mod._leer_log_panel()
        eventos_filtrados = panel_mod.filtrar_eventos_por_fecha(log, start, end)

        day_bars = _build_minute_map(log, start, end)

        return render_template(
            "barra_minuto.html",
            title="Barra Minuto",
            day_bars=day_bars,
            filtro_activo=filtro,
            start_date=start.isoformat() if start else "",
            end_date=end.isoformat() if end else "",
            ultimos_dias=ultimos_dias,
            total_eventos_filtrados=len(eventos_filtrados),
        )

