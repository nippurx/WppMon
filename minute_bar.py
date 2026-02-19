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


def _leer_log_panel_local(panel_mod):
    if hasattr(panel_mod, "_leer_log_panel"):
        return panel_mod._leer_log_panel()

    if not hasattr(panel_mod, "leer_log"):
        return []

    eventos = panel_mod.leer_log()
    if not eventos:
        return []
    return [ev for ev in eventos if len(ev) < 4 or not ev[3]]


def _extraer_gaps_simples_local(eventos):
    if not eventos:
        return []

    eventos_sorted = sorted(eventos, key=lambda x: x[0])
    offline_inicio = None
    gaps = []

    for ts, status, *_ in eventos_sorted:
        if status == "offline":
            offline_inicio = ts
        elif status == "online" and offline_inicio is not None:
            duracion = ts - offline_inicio
            if duracion.total_seconds() >= 1:
                gaps.append({"inicio": offline_inicio, "fin": ts, "duracion": duracion})
            offline_inicio = None

    if offline_inicio is not None:
        fin = datetime.now()
        duracion = fin - offline_inicio
        if duracion.total_seconds() >= 1:
            gaps.append({"inicio": offline_inicio, "fin": fin, "duracion": duracion})

    return gaps


def _build_items_from_sesiones_gaps(sesiones, gaps_simples, start, end):
    items = []

    for s in sesiones or []:
        inicio = s.get("inicio")
        fin = s.get("fin")
        duracion = s.get("duracion")
        if inicio is not None:
            items.append(
                {
                    "tipo": "online",
                    "inicio": inicio,
                    "fin": fin,
                    "duracion": duracion,
                }
            )

    for g in gaps_simples:
        items.append(
            {
                "tipo": "offline",
                "inicio": g["inicio"],
                "fin": g["fin"],
                "duracion": g["duracion"],
            }
        )

    if start and end:
        items = [it for it in items if it.get("inicio") and start <= it["inicio"].date() <= end]

    items = sorted(items, key=lambda x: x["inicio"], reverse=True)
    return items


def _build_items_cronologico_source(panel_mod, log, start, end):
    sesiones = panel_mod.generar_sesiones(log)
    gaps_simples = (
        panel_mod._extraer_gaps_simples(log)
        if hasattr(panel_mod, "_extraer_gaps_simples")
        else _extraer_gaps_simples_local(log)
    )
    return _build_items_from_sesiones_gaps(sesiones, gaps_simples, start, end), sesiones, gaps_simples


def _build_items_cronologico_reference(sesiones, gaps_simples, start, end):
    return _build_items_from_sesiones_gaps(sesiones, gaps_simples, start, end)


def _assert_items_match_cronologico(start, end, built_items, sesiones, gaps_simples):
    check_day = datetime.now().date()
    if not (start and end and start <= check_day <= end):
        check_day = start
    if check_day is None:
        return

    expected = _build_items_cronologico_reference(sesiones, gaps_simples, check_day, check_day)
    actual = [it for it in built_items if it.get("inicio") and it["inicio"].date() == check_day]

    expected_tuples = [(it["tipo"], it["inicio"], it["fin"]) for it in expected]
    actual_tuples = [(it["tipo"], it["inicio"], it["fin"]) for it in actual]
    if expected_tuples != actual_tuples:
        raise AssertionError("Barra Minuto: items no coinciden exactamente con cronologico.")


def _new_day_buckets(day_date):
    day_start = datetime.combine(day_date, datetime.min.time())
    out = []
    for minute_index in range(MINUTES_PER_DAY):
        start_minute = day_start + timedelta(minutes=minute_index)
        end_minute = start_minute + timedelta(minutes=1)
        out.append(
            {
                "minute_index": minute_index,
                "label_start": start_minute.strftime("%H:%M:%S"),
                "label_end": (end_minute - timedelta(seconds=1)).strftime("%H:%M:%S"),
                "state": "special",
                "_point": start_minute + timedelta(seconds=30),
                "block_tipo": "",
                "block_inicio": "",
                "block_fin": "",
                "block_duracion_str": "",
            }
        )
    return out


def _format_duration_hm(valor):
    if valor is None:
        return ""
    segundos = int(valor.total_seconds()) if hasattr(valor, "total_seconds") else None
    if segundos is None:
        return str(valor)
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


def _clip_blocks_for_day(items, day_start, day_end):
    blocks = []
    invalid_ranges = []
    for item in items:
        inicio = item.get("inicio")
        fin = item.get("fin")
        tipo = item.get("tipo")
        if tipo not in {"online", "offline"}:
            continue
        if inicio is None or fin is None or fin <= inicio:
            if inicio is None and fin is None:
                invalid_ranges.append((day_start, day_end))
                continue

            inv_start = inicio if inicio is not None else day_start
            inv_end = fin if fin is not None else day_end

            if inicio is not None and fin is not None and fin <= inicio:
                inv_end = inicio + timedelta(minutes=1)

            inv_start = max(inv_start, day_start)
            inv_end = min(inv_end, day_end)
            if inv_end <= inv_start:
                inv_end = min(day_end, inv_start + timedelta(minutes=1))
            if inv_end > inv_start:
                invalid_ranges.append((inv_start, inv_end))
            continue
        seg_inicio = max(inicio, day_start)
        seg_fin = min(fin, day_end)
        if seg_fin <= seg_inicio:
            continue
        blocks.append(
            {
                "tipo": tipo,
                "inicio_clip": seg_inicio,
                "fin_clip": seg_fin,
                "inicio_real": inicio,
                "fin_real": fin,
                "duracion_real": item.get("duracion"),
                "duracion_str": _format_duration_hm(item.get("duracion")),
            }
        )
    blocks.sort(key=lambda x: x["inicio_clip"])
    return blocks, invalid_ranges


def _find_blocks_for_point(blocks, point):
    return [b for b in blocks if b["inicio_clip"] <= point < b["fin_clip"]]


def _set_bucket_from_block(bucket, block):
    bucket["state"] = block["tipo"]
    bucket["block_tipo"] = block["tipo"]
    bucket["block_inicio"] = block["inicio_real"].strftime("%H:%M:%S")
    bucket["block_fin"] = block["fin_real"].strftime("%H:%M:%S")
    bucket["block_duracion_str"] = block["duracion_str"]


def _point_is_in_invalid_range(point, invalid_ranges):
    for inv_start, inv_end in invalid_ranges:
        if inv_start <= point < inv_end:
            return True
    return False


def _finalize_day_buckets(buckets, day_blocks, invalid_ranges):
    total_online = 0
    total_offline = 0
    special_minutes = 0
    for block in day_blocks:
        overlap_s = int((block["fin_clip"] - block["inicio_clip"]).total_seconds())
        if overlap_s <= 0:
            continue
        if block["tipo"] == "online":
            total_online += overlap_s
        else:
            total_offline += overlap_s

    for b in buckets:
        b["block_tipo"] = ""
        b["block_inicio"] = ""
        b["block_fin"] = ""
        b["block_duracion_str"] = ""
        b["state"] = "special"
        point = b["_point"]
        try:
            if _point_is_in_invalid_range(point, invalid_ranges):
                special_minutes += 1
                continue

            matching_blocks = _find_blocks_for_point(day_blocks, point)
            if len(matching_blocks) == 1:
                _set_bucket_from_block(b, matching_blocks[0])
            else:
                special_minutes += 1
        except Exception:
            special_minutes += 1
        finally:
            b.pop("_point", None)
    return total_online, total_offline, special_minutes


def _build_day_bars_from_items(panel_mod, items, start, end):
    day_labels = getattr(panel_mod, "DAY_LABELS", ["lun", "mar", "mie", "jue", "vie", "sab", "dom"])
    day_bars = []
    day = start
    while day <= end:
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        buckets = _new_day_buckets(day)
        day_blocks, invalid_ranges = _clip_blocks_for_day(items, day_start, day_end)
        total_online, total_offline, special_minutes = _finalize_day_buckets(
            buckets, day_blocks, invalid_ranges
        )
        day_bars.append(
            {
                "date": day.isoformat(),
                "day_label": f"{day_labels[day.weekday()]} {day.isoformat()}",
                "buckets": buckets,
                "blocks": day_blocks,
                "total_online_seconds": total_online,
                "total_offline_seconds": total_offline,
                "special_minutes": special_minutes,
            }
        )
        day += timedelta(days=1)
    return day_bars


def register_minute_bar(app):
    @app.route("/barra-minuto")
    def barra_minuto():
        panel_mod = _resolve_panel_module()
        start, end, filtro = panel_mod.obtener_rango_fechas(request)
        ultimos_dias = panel_mod.obtener_ultimos_5_dias()

        log = _leer_log_panel_local(panel_mod)
        items, sesiones, gaps_simples = _build_items_cronologico_source(panel_mod, log, start, end)
        _assert_items_match_cronologico(start, end, items, sesiones, gaps_simples)
        day_bars = _build_day_bars_from_items(panel_mod, items, start, end)

        return render_template(
            "barra_minuto.html",
            title="Barra Minuto",
            day_bars=day_bars,
            filtro_activo=filtro,
            start_date=start.isoformat() if start else "",
            end_date=end.isoformat() if end else "",
            ultimos_dias=ultimos_dias,
        )
