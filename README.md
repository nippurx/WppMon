```markdown
# 📡 WppMon — Sistema de Monitoreo y Análisis de Presencia de WhatsApp Web  
### Versión 2.0 — Arquitectura Modular + Panel Web Avanzado

https://chatgpt.com/g/g-p-69230e2c01b481918c0de7d7dc2d5e2c-whatsapp-monitor/project

WppMon es un sistema de monitoreo pasivo de presencia en WhatsApp Web.  
Captura eventos *online/offline* y los procesa mediante un panel web avanzado que permite obtener métricas, inferir patrones de uso y detectar comportamientos relevantes.

---

# 📁 Estructura del Proyecto

```

WppMon/
│
├── wppmon.py                # Captura presencia y genera whatsapp_presence_log.csv
│
├── panel.py                 # Servidor Flask: UI + rutas + procesamiento
├── analyzer.py              # Parsing del CSV + sesiones + exportación JSON
├── detectors.py             # Lógica avanzada: gaps, charlas, métricas
│
├── config.json              # Parámetros configurables del panel
│
├── /templates               # HTML Jinja2 para el panel
│   ├── base.html
│   ├── index.html
│   ├── sesiones.html
│   ├── gaps.html
│   ├── timeline.html
│   ├── heatmap.html
│   ├── sospechosas.html
│   ├── metricas.html
│   ├── dia.html
│   └── config.html
│
├── /static
│   ├── styles.css           # Diseño C1 Hacker Pro
│   ├── online.wav           # Sonidos (no generados por panel)
│   └── offline.wav
│
├── whatsapp_presence_log.csv
└── /data/json_diario        # Exportaciones automáticas por día

```

---

# 🔥 Flujo General del Sistema

```

WhatsApp Web → wppmon.py → whatsapp_presence_log.csv
↓
panel.py (Flask)
↓
analyzer.py (parsear + sesiones)
↓
detectors.py (IA estadística)
↓
Panel Web (HTML)

```

---

# 🧩 Componentes Principales

---

# 1) wppmon.py — **Captura de presencia**

Es el *monitor real*.  
Define cuándo WhatsApp Web muestra “online” y “offline”.

Genera 2 archivos:

- `whatsapp_presence_log.csv`
- `estado_actual.json`

Formato del CSV:

```

timestamp,status
dom 2025-11-23 12:01:47,offline
dom 2025-11-23 12:01:56,online

```

**NOTA:**  
El prefijo del día (lun/mar/mie/jue/vie/sab/dom) es parte del dato original  
y debe preservarse.

---

# 2) panel.py — **Servidor Web (Flask)**

Es el núcleo del sistema visual.  
Hace:

- Carga del log CSV  
- Reprocesamiento de sesiones  
- Generación automática de JSON diarios  
- Rutas del servidor  
- Render de plantillas  
- Lectura/guardado de configuración  
- Exposición de vistas interactivas  
- Dashboard del historial

### Rutas principales:

| Ruta | Función |
|------|---------|
| `/` | Home, resumen general |
| `/sesiones` | Lista completa de sesiones |
| `/gaps` | Gaps de sueño, sospechosos, rojos, cita |
| `/sospechosas` | Charlas largas, muy largas, íntimas |
| `/timeline` | Barras de actividad por día |
| `/heatmap` | Frecuencia por hora del día |
| `/metricas` | Métricas psicológicas estadísticas |
| `/dia/<fecha>` | Informe diario + download JSON |
| `/config` | Ajuste de parámetros |
| `/config-save` | Guardado de parámetros |

### JSON automático:

`panel.py` genera JSON diarios en:

```

/data/json_diario/YYYY-MM-DD.json

```

cada vez que inicia o cada vez que se llama a ciertas rutas.

---

# 3) analyzer.py — **Parseo del CSV + Sesiones + Exportación JSON**

Este módulo es responsable del **procesamiento crudo del log**.

### Funciones principales:

### ✔ `leer_log()`
- Lee `whatsapp_presence_log.csv`
- Detecta formato con prefijo de día (“dom 2025-11-23 ...”)
- Separa `dia_texto` del timestamp real
- Devuelve:

```

[(datetime, status, dia_texto), ...]

```

### ✔ `generar_sesiones(eventos)`
Detecta:

- inicio de sesión = primer “online”
- fin de sesión = siguiente “offline”

Devuelve:

```

[
{
"inicio": datetime,
"inicio_dia": "dom",
"fin": datetime,
"fin_dia": "dom",
"duracion": timedelta
}
]

```

### ✔ `exportar_json_dia(fecha, config)`
Genera un JSON completo de:

- sesiones del día  
- gaps clasificados  
- charlas largas / muy largas / íntimas  
- métricas estadísticas  
- resumen del día  

---

# 4) detectors.py — **Inteligencia estadística**

Este archivo contiene TODA la lógica de análisis inteligente.

### ✔ `clasificar_gaps(eventos, config)`
Detecta:

- sueño (> X horas)
- sospechoso (> X minutos)
- rojo (> Y minutos)
- cita (> Z minutos)

### ✔ `detectar_charlas_avanzado(sesiones, config)`
Detecta:

- charlas largas (≥ 20 min)
- muy largas (≥ 45 min)
- íntimas (≥ 60 min)
- sospechosas (larga + horario 22–03)

### ✔ `metricas_psicologicas(sesiones, config)`
Devuelve:

```

{
intensidad: 0–100,
sincronia: 0–100,
variacion: 0–100,
riesgo_tercero: "bajo/medio/alto/critico"
}

````

**Nota:**  
Estas métricas son *estadísticas*, NO interpretación emocional humana.

---

# 5) Plantillas HTML (Jinja2) — **Interfaz del Panel**

### 5.1 base.html
Layout principal:
- CSS
- menú superior
- bloques de contenido
- diseño móvil

### 5.2 index.html
Resumen general.

### 5.3 sesiones.html
Lista todas las sesiones (inicio/fin/duración).

### 5.4 gaps.html
Listas clasificadas:
- sueño  
- sospechosos  
- rojos  
- cita  

### 5.5 sospechosas.html
Charlas largas, muy largas, íntimas.

### 5.6 timeline.html
Barras proporcionales por día y hora.

### 5.7 heatmap.html
Frecuencias por hora (matriz 0–23h).

### 5.8 metricas.html
Métricas psicológicas estadísticas.

### 5.9 dia.html
Informe diario completo + JSON.

### 5.10 config.html
Modificar parámetros del sistema.

---

# 6) config.json — **Parámetros configurables**

Ejemplo:

```json
{
  "gap_sueno_horas": 5,
  "gap_sospechoso_min": 15,
  "gap_rojo_min": 45,
  "gap_cita_min": 90,
  "charla_larga_min": 20,
  "charla_muy_larga_min": 45,
  "charla_intima_min": 60
}
````

Se edita desde `/config`.

---

# 🔥 Datos Técnicos Importantes Para Desarrolladores

### 1. Los timestamps del CSV **incluyen el nombre del día**

Ejemplo:

```
dom 2025-11-23 12:01:47
```

El sistema:

* separa `"dom"`
* parsea `"2025-11-23 12:01:47"`
* guarda ambos

### 2. analyzer.py y panel.py deben manejar tuplas de 3 elementos:

```
(ts, estado, dia_texto)
```

### 3. Al exportar JSON diario, `fecha` debe ser un `datetime.date`, NO un string.

### 4. Gaps y charlas dependen del `config.json`.

### 5. Todos los errores comunes derivan de:

* cambios en el formato CSV
* no importar funciones de detectors
* pasar `fecha` como string en vez de datetime
* intentar parsear timestamps sin remover el prefijo del día

---

# 🧪 Ejecución

## Monitoreo:

```
py wppmon.py
```

## Panel:

```
py panel.py
```

Panel accesible en:

```
http://127.0.0.1:5000
http://192.168.0.14:5000
```

---

# 🛠 Posibles Mejoras Futuras

* Watchdog para wppmon.py
* Detección automática de patrones de cita
* API REST para exportar sesiones
* Autorefresh del panel
* Gráficos generados por JS opcional
* Machine learning (opcional)

---

# 🤝 Contribución

Este README está diseñado para que **OpenAI Codex, ChatGPT, GPT-4, GPT-5 y cualquier modelo** puedan entender completamente la arquitectura del proyecto y ayudarte a:

* depurar bugs
* mejorar compatibilidad
* agregar nuevas funciones
* detectar errores de tipado
* interpretar logs incorrectos
* corregir módulos desincronizados

---


Perfecto Fer.
Acá tenés **el DIAGRAMA DE FLUJO ASCII profesional**, claro, estructurado y legible para cualquier desarrollador o modelo de IA.

Este diagrama describe **todo el flujo del sistema**, desde la captura hasta el análisis final, incluyendo:

* wppmon.py
* analyzer.py
* detectors.py
* panel.py
* templates
* config.json
* archivos producidos

---

# ⭐ **DIAGRAMA DE FLUJO ASCII COMPLETO PARA README.md**

Copialo así tal cual en tu README.

```markdown
# 📉 Diagrama de Flujo (ASCII)

```

```
                   ┌────────────────────────────┐
                   │      WhatsApp Web          │
                   │ (estado: online/offline)   │
                   └───────────────┬────────────┘
                                   │
                                   ▼
                     ┌────────────────────────┐
                     │       wppmon.py        │
                     │  (monitor en tiempo    │
                     │          real)         │
                     └─────────────┬──────────┘
                                   │
                 escribe CSV       │      escribe estado
                                   │
                                   ▼
          ┌───────────────────────────────────────────────┐
          │        whatsapp_presence_log.csv               │
          │   dom 2025-11-23 12:01:47,offline              │
          │   dom 2025-11-23 12:01:56,online               │
          └──────────────────────────┬─────────────────────┘
                                     │
                       panel.py lee  │  con analyzer.py
                                     ▼
                  ┌──────────────────────────────┐
                  │         analyzer.py           │
                  │──────────────────────────────│
                  │ leer_log():                   │
                  │  - separa “dom” del timestamp │
                  │  - parsea fecha y hora        │
                  │  - retorna (ts, estado, día)  │
                  │                                │
                  │ generar_sesiones():            │
                  │  - detecta inicios y fines     │
                  │  - calcula duraciones          │
                  │                                │
                  │ exportar_json_dia():           │
                  │  - mezcla sesiones, gaps,      │
                  │    charlas y métricas          │
                  │  - genera JSON diarios         │
                  └───────────────┬────────────────┘
                                  │
          usa lógica avanzada     │
                                  ▼
               ┌──────────────────────────────────────┐
               │             detectors.py              │
               │──────────────────────────────────────│
               │ clasificar_gaps():                    │
               │   - sueño (> X horas)                 │
               │   - sospechosos (> Y min)             │
               │   - rojos (> Z min)                   │
               │   - cita (≥ 90 min)                   │
               │                                       │
               │ detectar_charlas_avanzado():          │
               │   - largas (20+)                      │
               │   - muy largas (45+)                  │
               │   - íntimas (60+)                     │
               │   - nocturnas sospechosas             │
               │                                       │
               │ metricas_psicologicas():              │
               │   - intensidad                        │
               │   - variación                         │
               │   - sincronía                         │
               │   - riesgo estadístico                │
               └───────────────────┬────────────────────┘
                                   │
                       panel.py combina todos los datos
                                   │
                                   ▼
         ┌────────────────────────────────────────────────┐
         │      data/json_diario/YYYY-MM-DD.json          │
         │ (exportación diaria para análisis profundo)    │
         └───────────────────────────┬────────────────────┘
                                     │
                         panel.py renderiza HTML
                                     │
                                     ▼
            ┌─────────────────────────────────────────────┐
            │                   /templates                │
            │────────────────────────────────────────────│
            │ base.html           → diseño general        │
            │ index.html          → resumen general       │
            │ sesiones.html       → sesiones por fecha    │
            │ gaps.html           → sueño / sospechosos   │
            │ sospechosas.html    → charlas largas        │
            │ timeline.html        → barras de actividad   │
            │ heatmap.html         → uso por hora          │
            │ metricas.html        → métricas estadísticas │
            │ dia.html             → informe diario        │
            │ config.html          → parámetros del sistema│
            └──────────────────────┬──────────────────────┘
                                   │
                                   ▼
              ┌────────────────────────────────────┐
              │        Navegador Web (UI)          │
              │   http://127.0.0.1:5000            │
              │   http://192.168.0.14:5000         │
              └────────────────────────────────────┘
```

```

---

# 👌 Este diagrama:

- Resume TODO el flujo del sistema
- Es perfectamente entendible para modelos de IA
- Deja claro qué hace cada archivo
- Indica qué datos se esperan y en qué formato
- Muestra la arquitectura modular
- Permite encontrar errores de sincronización entre módulos
- Sirve para debugging estructurado

---

## FEATURES

1. todas las paginas del panel deben actualizarse cada 5 segundos para estar actualizadas

2. los liistados deben estar ordenados de mas reciente a mas antigua, para ver los ultimos datos arriba sin tener que scrollear

3. en todos los listados que aparezcan los tiempos de charlas deben colorearse siguiendo las reglas de /sospechosas  (amarillos , roja , etc)

4. aumentar el tamaño de font de los listados con fechas y tiempos para mejorar legibilidad.   Debe poder ajustarse em /config

5. en la pagina principal.  Debajos de 
Último cambio:
vie 2025-11-28 12:31:25
debe indicarse el gap offline desde la desconeccion en horas y minutos ignorar segundos.  deben colorearse segun las reglas de /gaps (amarillo, rojo, etc)
si es menor a Gap sospechoso (minutos) debe estar verde de fondo.

correccion a pagina princial
si esta online
mostrar:  Online desde hace (tiempo  1 h 2 m) (color verde)
si esta offline
mostrar:  Offline desde hace (tiempo  1 h 2 m) (color rojo)
