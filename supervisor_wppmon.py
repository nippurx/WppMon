import os
import csv
import time
import subprocess
import datetime
import ctypes

# =========================
# CONFIG
# =========================
LOG_CSV = "whatsapp_presence_log.csv"

# Tu BAT que abre Edge directo al chat (ponelo con ruta absoluta si no corre desde el mismo folder)
EDGE_BAT = r"edge-wppmon.bat"

# Cada cuánto chequea el CSV
CHECK_INTERVAL = 60  # segundos

# Si el último estado es offline y pasaron más de X minutos desde ese evento -> reiniciar Edge
OFFLINE_UMBRAL_MIN = 15

# Para no reiniciar cada 10s cuando ya se pasó el umbral:
# mientras siga offline, reinicia como máximo 1 vez cada X minutos
RESTART_COOLDOWN_MIN = 15

# =========================
# UTILIDADES
# =========================
def popup(msg, title="WppMon Supervisor"):
    try:
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)
    except Exception:
        pass

def log_evento(msg):
    with open("supervisor_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat(sep=' ', timespec='seconds')} - {msg}\n")

def matar_edge():
    # Mata Edge sí o sí (PC dedicada, como dijiste)
    os.system("taskkill /IM msedge.exe /F")

def ejecutar_bat(bat_path: str):
    # Ejecuta el .bat (cmd /c) y no se queda esperando
    subprocess.Popen(["cmd.exe", "/c", bat_path], shell=False)

def parsear_timestamp(raw: str):
    """
    Formato esperado en el CSV (según tu proyecto):
      'dom 2025-11-23 12:01:47'  o  '2025-11-23 12:01:47'
    """
    raw = (raw or "").strip()

    if not raw:
        return None

    # Si empieza con dia abreviado, lo sacamos
    partes = raw.split(" ", 1)
    if len(partes) == 2 and len(partes[0]) == 3:  # 'lun','mar','mie',...
        raw_dt = partes[1].strip()
    else:
        raw_dt = raw

    # Soporta 'YYYY-MM-DD HH:MM:SS' o ISO
    try:
        return datetime.datetime.fromisoformat(raw_dt)
    except Exception:
        return None

def leer_ultimo_evento_csv(csv_path: str):
    """
    Devuelve (timestamp, status) del último registro válido.
    Status se normaliza a 'online'/'offline'.
    """
    if not os.path.exists(csv_path):
        return None, None

    ultimo_ts = None
    ultimo_status = None

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        # salta header si existe
        header = next(reader, None)

        for row in reader:
            if not row or len(row) < 2:
                continue

            ts_raw = row[0].strip()
            st_raw = row[1].strip().lower()

            ts = parsear_timestamp(ts_raw)
            if ts is None:
                continue

            if st_raw not in ("online", "offline"):
                continue

            if (ultimo_ts is None) or (ts >= ultimo_ts):
                ultimo_ts = ts
                ultimo_status = st_raw

    return ultimo_ts, ultimo_status

# =========================
# MAIN
# =========================
print("Supervisor WppMon (modo reinicio por offline>15min) iniciado...")
log_evento("Supervisor iniciado.")

last_restart_at = None

while True:
    time.sleep(CHECK_INTERVAL)

    ts, status = leer_ultimo_evento_csv(LOG_CSV)
    if ts is None or status is None:
        continue

    ahora = datetime.datetime.now()
    edad_min = (ahora - ts).total_seconds() / 60.0

    if status == "offline" and edad_min >= OFFLINE_UMBRAL_MIN:
        # cooldown para reiniciar como mucho cada 15 min mientras siga offline
        if last_restart_at is None:
            puede = True
        else:
            puede = (ahora - last_restart_at).total_seconds() >= (RESTART_COOLDOWN_MIN * 60)

        if puede:
            msg = f"OFFLINE hace {int(edad_min)} min (desde {ts}). Reinicio Edge + BAT."
            print("⚠️", msg)
            log_evento(msg)

            # popup("Offline > 15 min. Reiniciando Edge…", "WppMon Supervisor")

            matar_edge()
            time.sleep(1)
            ejecutar_bat(EDGE_BAT)

            last_restart_at = ahora

