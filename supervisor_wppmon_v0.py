import time
import os
import subprocess
import datetime
import ctypes

# ARCHIVOS DEL SISTEMA
LOG = "whatsapp_presence_log.csv"
ESTADO = "estado_actual.json"
WPPMON = "wppmon.py"

# CONFIG
MAX_SILENCIO = 60        # segundos sin cambios en el CSV
MAX_ESTADO_GAP = 60      # segundos sin actualización en estado_actual.json
CHECK_INTERVAL = 10      # cada cuánto chequea
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PYTHON_PATH = r"C:\Users\marpec\AppData\Local\Programs\Python\Python310\python.exe"

def popup(msg, title="WppMon Supervisor"):
    ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)

def leer_timestamp_archivo(path):
    if not os.path.exists(path):
        return None
    return os.path.getmtime(path)

def arrancar_edge():
    os.system("taskkill /IM msedge.exe /F")
    time.sleep(1)
    subprocess.Popen([
		EDGE_PATH,
		"https://web.whatsapp.com/send?phone=+5491144381917"
	])


def arrancar_monitor():
    subprocess.Popen([PYTHON_PATH, WPPMON])

def log_evento(msg):
    with open("supervisor_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now()} - {msg}\n")

print("Supervisor WppMon iniciado...")
log_evento("Supervisor iniciado.")

# ============================================================
# LOOP PRINCIPAL
# ============================================================
ultimo_csv = leer_timestamp_archivo(LOG)
ultimo_estado = leer_timestamp_archivo(ESTADO)

while True:
    time.sleep(CHECK_INTERVAL)

    # ------------------------------
    # CHECK CSV
    # ------------------------------
    ts_csv = leer_timestamp_archivo(LOG)

    if ts_csv is not None and ultimo_csv is not None:
        silencio = time.time() - ts_csv

        if silencio > MAX_SILENCIO:
            msg = f"⚠️ WppMon no actualiza el CSV hace {int(silencio)}s"
            print(msg)
            log_evento(msg)

            # popup("El monitor dejó de registrar presencia. Reinicio Edge.", "WppMon Alerta")
            arrancar_edge()
            ultimo_csv = ts_csv
            continue

    ultimo_csv = ts_csv

    # ------------------------------
    # CHECK estado_actual.json
    # ------------------------------
    ts_estado = leer_timestamp_archivo(ESTADO)

    if ts_estado is not None and ultimo_estado is not None:
        gap = time.time() - ts_estado

        if gap > MAX_ESTADO_GAP:
            msg = f"⚠️ estado_actual.json no cambia hace {int(gap)}s."
            print(msg)
            log_evento(msg)

            # popup("El monitor parece congelado. Reiniciando WppMon…", "WppMon Supervisor")

            # Reiniciar el script principal
            os.system("taskkill /IM python.exe /F")
            time.sleep(1)
            arrancar_monitor()
            ultimo_estado = ts_estado
            continue

    ultimo_estado = ts_estado
