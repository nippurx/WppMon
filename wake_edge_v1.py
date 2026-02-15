import pyautogui
import time

# Desactiva failsafe SOLO para este script
pyautogui.FAILSAFE = False

print("Wake-Edge en ejecución...")

while True:
    # Movimiento suave para no pegar contra bordes
    pyautogui.moveRel(20, 0, duration=0.2)
    pyautogui.moveRel(-20, 0, duration=0.2)

    # Espera 15 segundos (ajustá si querés)
    time.sleep(15)

