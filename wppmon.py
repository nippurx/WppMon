import win32gui
import dxcam
import easyocr
import numpy as np
import cv2
import time
import datetime
import csv
import winsound
import os
import json




# Crear lector OCR
reader = easyocr.Reader(['es'])

# Crear capturador DXCAM
camera = dxcam.create(output_idx=0)


def limpiar_csv_inicial_avanzado():
    import csv
    from datetime import datetime

    LOG_FILE = "whatsapp_presence_log.csv"
    TEMP_FILE = "whatsapp_presence_log_temp.csv"

    if not os.path.exists(LOG_FILE):
        return

    # mapa dias espanol -> ingles para strptime
    dias_map = {
        "lun": "Mon",
        "mar": "Tue",
        "mie": "Wed",
        "jue": "Thu",
        "vie": "Fri",
        "sab": "Sat",
        "dom": "Sun"
    }

    def parse_ts(ts_raw):
        try:
            dia_esp = ts_raw[:3]
            dia_eng = dias_map.get(dia_esp, "Mon")
            ts_eng = ts_raw.replace(dia_esp, dia_eng)
            return datetime.strptime(ts_eng, "%a %Y-%m-%d %H:%M:%S")
        except:
            return None

    rows = []

    # ==== cargar todo ====
    with open(LOG_FILE, newline="", encoding="utf-8") as fin:
        reader = csv.reader(fin)
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            ts_raw = row[0]
            status = row[1]
            dt = parse_ts(ts_raw)
            if dt is None:
                continue
            rows.append([dt, ts_raw, status])

    # ==== ordenar ====
    rows.sort(key=lambda x: x[0])

    limpio = []
    last_status = None
    last_dt = None

    for dt, ts_raw, status in rows:

        # 1) eliminar ruido escribiendo
        if status == "escribiendo":
            continue

        # 2) eliminar timestamps fuera de orden
        if last_dt and dt < last_dt:
            continue

        # 3) eliminar micro-sesiones (< 6 segundos)
        if last_dt and last_status and status != last_status:
            delta = (dt - last_dt).total_seconds()
            if delta < 6:
                continue

        # 4) eliminar sesiones absurdamente largas (freeze)
        if last_dt and last_status == "online":
            delta = (dt - last_dt).total_seconds()
            if delta > 4 * 3600:  # 4 horas
                continue

        # 5) compactacion: ignorar estados repetidos
        if status == last_status:
            continue

        limpio.append([ts_raw, status])
        last_status = status
        last_dt = dt

    # ==== guardar ====
    with open(TEMP_FILE, "w", newline="", encoding="utf-8") as fout:
        writer = csv.writer(fout)
        writer.writerow(["timestamp", "status"])
        writer.writerows(limpio)

    os.replace(TEMP_FILE, LOG_FILE)
    print(">>> Limpieza avanzada inicial del CSV completada.")
    print(f">>> Total de lineas limpias: {len(limpio)}")




def play_sound_online():
    try:
        winsound.PlaySound("online.wav", winsound.SND_FILENAME | winsound.SND_ASYNC)
    except:
        print("No se pudo reproducir online.wav")

def play_sound_offline():
    try:
        winsound.PlaySound("offline.wav", winsound.SND_FILENAME | winsound.SND_ASYNC)
    except:
        print("No se pudo reproducir offline.wav")



def find_whatsapp_edge_window():
    windows = []

    def enum_handler(hwnd, ctx):
        title = win32gui.GetWindowText(hwnd).lower()
        if "whatsapp" in title and "edge" in title:
            windows.append(hwnd)

    win32gui.EnumWindows(enum_handler, None)
    return windows[0] if windows else None


def get_window_rect(hwnd):
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    return left, top, width, height


def autodetect_status_area(left, top, width, height):
    # Basado en zoom 110%
    rel_x = int(width * 0.18)
    rel_y = int(height * 0.125)
    rel_w = int(width * 0.23)
    rel_h = int(height * 0.06)

    abs_x1 = left + rel_x
    abs_y1 = top + rel_y
    abs_x2 = abs_x1 + rel_w
    abs_y2 = abs_y1 + rel_h

    return (abs_x1, abs_y1, abs_x2, abs_y2)


def capture_region(region):
    x1, y1, x2, y2 = region
    frame = camera.grab(region=region)
    if frame is None:
        return None
    return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)



def check_online(img):
    result = reader.readtext(img)
    text = " ".join([r[1].lower() for r in result])

    if "en linea" in text or "en línea" in text:
        return "online"
    if "escribiendo" in text:
        return "escribiendo"
    return "offline"


def _cargar_ultimo_estado(csv_file):
    """
    Recupera el ultimo status conocido para evitar registrar duplicados
    al reiniciar el monitor (ej. offline -> offline).
    """
    ultimo = ""

    try:
        if os.path.exists("estado_actual.json"):
            with open("estado_actual.json", "r", encoding="utf-8") as jf:
                ultimo = json.load(jf).get("status", "") or ultimo
    except Exception:
        ultimo = ""

    if ultimo:
        return ultimo

    if not os.path.exists(csv_file):
        return ultimo

    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 2:
                    ultimo = row[1].strip().lower() or ultimo
    except Exception:
        ultimo = ""

    return ultimo
    
def _borrar_ultimo_online(csv_file):
	"""
	Si el último evento del CSV es 'online', borrar completamente esa línea
	para evitar sesiones falsas cuando aparezca el RESTART.
	"""
	if not os.path.exists(csv_file):
		return

	with open(csv_file, "r", encoding="utf-8") as f:
		rows = list(csv.reader(f))

	if len(rows) <= 1:
		# Solo header o vacío
		return

	ultima = rows[-1]
	# ultima = ["jue 2025-12-04 10:58:36", "online"] o con etiquetas extras
	if len(ultima) >= 2 and ultima[1].strip().lower() == "online":
		# Borrar última línea
		print(">>> Último evento era ONLINE. Eliminando para evitar sesión falsa.")
		rows = rows[:-1]
		with open(csv_file, "w", newline="", encoding="utf-8") as f:
			writer = csv.writer(f)
			writer.writerows(rows)    


def main():
    print("Buscando ventana de WhatsApp Web en Edge...")

    # limpiar_csv_inicial_avanzado()

    hwnd = None
    while hwnd is None:
        hwnd = find_whatsapp_edge_window()
        if hwnd is None:
            print("Abra WhatsApp Web en Edge.")
            time.sleep(3)

        print("Ventana encontrada:", hwnd)


    # Captura pantalla completa para determinar tamano
    print("Determinando tamano de pantalla...")
    test_screen = camera.grab()
    if test_screen is None:
        print("DXCAM no puede capturar pantalla completa.")
        exit()

    h, w = test_screen.shape[0], test_screen.shape[1]

    # Region superior de 250 px
    region = (0, 0, w, 178)    # solo parte superior

    print("Usando region SUPERIOR reducida:", region)


    csv_file = "whatsapp_presence_log.csv"

    if not os.path.exists(csv_file) or os.path.getsize(csv_file) == 0:
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "status", "restart"])

    last_status = _cargar_ultimo_estado(csv_file)

    # BORRAR ULTIMA LINEA SI ES ONLINE (para que RESTART no genere sesión gigante)
    _borrar_ultimo_online(csv_file)

    restart_pendiente = True

    
    def guardar_evento(ts, status, es_restart=False):
        fila = [ts, status]
        if es_restart:
            fila.append("RESTART")
        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fila)

    print("Iniciando monitoreo...")

    while True:
        img = capture_region(region)
        if img is None:
            print("Error capturando pantalla.")
            time.sleep(1)
            continue

        status = check_online(img)

        dias = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]
        dia_semana = dias[datetime.datetime.now().weekday()]
        timestamp = datetime.datetime.now().strftime(f"{dia_semana} %Y-%m-%d %H:%M:%S")


        print(f"[{timestamp}] {status}")

        if restart_pendiente:
            guardar_evento(timestamp, status, es_restart=True)
            with open("estado_actual.json", "w") as jf:
                json.dump({"timestamp": timestamp, "status": status}, jf)
            last_status = status
            restart_pendiente = False
            time.sleep(2)
            continue

        if status != last_status:

            # Sonido segun estado
            if status == "online":
                play_sound_online()
            elif status == "offline":
                play_sound_offline()

            # Guardar en CSV
            guardar_evento(timestamp, status, es_restart=False)
            print(f">>> Cambio detectado: {last_status or 'n/a'} -> {status} (guardado)")
                
            # Guardar estado actual en JSON para el servidor web
            with open("estado_actual.json", "w") as jf:
                json.dump({"timestamp": timestamp, "status": status}, jf)

        last_status = status
        time.sleep(2)






if __name__ == "__main__":
    main()
