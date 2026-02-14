#
# stats de log de whatsapp
# https://grok.com/c/6f91e4c5-eec2-4ac5-802a-e6bb049aec8d?rid=fa5a02b7-fadd-43a8-8a55-c8cdb39c0c4c
#

import csv
from datetime import datetime

months = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril', 5: 'mayo', 6: 'junio',
    7: 'julio', 8: 'agosto', 9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
}
weekdays = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']

with open('whatsapp_presence_log.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    logs = []
    for row in reader:
        row = [field.strip() for field in row if field.strip()]
        if len(row) != 2:
            continue
        timestamp_str, status = row
        parts = timestamp_str.split()
        day_abbr = parts[0]
        date_str = parts[1]
        time_str = parts[2]
        dt = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S')
        logs.append((dt, status))

# Process logs
with open('whatsapp_presence_log.tsv', 'w') as out:
    out.write('fecha\taño\tmes\tfechanum\tdia\ttipo\tinicio\tfin\tduracion\tduracion_num\n')
    if not logs:
        pass
    prev_dt, prev_status = logs[0]
    for dt, status in logs[1:]:
        if status == prev_status:
            continue
        delta = dt - prev_dt
        total_seconds = delta.total_seconds()
        duracion_num = total_seconds / 60
        hours = int(total_seconds // 3600)
        remainder = total_seconds % 3600
        if hours > 0:
            minutes = int(remainder // 60)
            dur_str = f"{hours} h {minutes} m" if minutes > 0 else f"{hours} h"
        else:
            minutes = int(total_seconds // 60)
            seconds = int(total_seconds % 60)
            if minutes > 0:
                dur_str = f"{minutes} m {seconds} s" if seconds > 0 else f"{minutes} m"
            else:
                dur_str = f"{seconds} s"
        fecha = prev_dt.strftime('%Y-%m-%d')
        ano = prev_dt.year
        mes = months[prev_dt.month]
        fechanum = prev_dt.day
        dia = weekdays[prev_dt.weekday()]
        inicio = prev_dt.strftime('%H:%M')
        fin = dt.strftime('%H:%M')
        out.write(f"{fecha}\t{ano}\t{mes}\t{fechanum}\t{dia}\t{prev_status}\t{inicio}\t{fin}\t{dur_str}\t{duracion_num}\n")
        prev_dt, prev_status = dt, status
