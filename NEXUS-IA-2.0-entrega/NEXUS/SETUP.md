# SETUP.md — Instalación y arranque de NEXUS IA 2.0

## Requisitos

- Python **3.11 a 3.13** (comprobado por `setup.py`; por debajo de 3.11 aborta con
  error explícito, por encima de 3.13 avisa pero continúa).
- Windows, macOS o Linux — `requirements.txt` filtra automáticamente los paquetes
  específicos de Windows mediante `sys_platform` markers.
- Una API key de Gemini (gratuita) — se pide en el primer arranque, no antes.

## Instalación (una sola vez)

```bash
python setup.py
```

Esto hace, en este orden:
1. Comprueba la versión de Python.
2. `pip install -r requirements.txt` (el propio fichero filtra por sistema operativo).
3. Descarga los navegadores de Playwright (chromium + firefox) para `browser_control`.
   Si falla (red corporativa, sin conexión), **no aborta la instalación** — avisa y
   dice cómo reintentar luego: todo excepto la automatización de navegador sigue
   funcionando.
4. Comprueba que `core/face_model.obj` (el modelo 3D del avatar) esté presente y no
   truncado; si falta, avisa que el HUD caerá al modo "core" (esfera, sin cara).
5. Notas específicas de SO por consola (Windows: registro de `pywin32`; Linux:
   paquetes nativos recomendados para volumen/brillo/recordatorios; macOS: nada
   adicional necesario).

## Arranque

```bash
python main.py
```

- Primer arranque: `ui.wait_for_api_key()` bloquea hasta que pegues tu API key de
  Gemini en la pantalla de configuración. Se guarda en `config/api_keys.json`.
- Arranques siguientes: usa la key guardada y conecta directamente.
- El wake word ("Hey Jarvis") es **opcional y off por defecto** — se activa desde
  ⚙ → WAKE WORD dentro de la app, que instala `openwakeword` (pip) y descarga el
  modelo (unos pocos MB) bajo demanda.

## No hay un "cliente móvil" que arrancar por separado

Esto es importante y a menudo se malinterpreta: **no existe un ejecutable ni un
comando distinto para el móvil.** El servidor del dashboard
(`dashboard/server.py`, FastAPI/uvicorn) se levanta automáticamente dentro del
mismo proceso `python main.py` — ver `VoiceEngine.run()`, que hace
`asyncio.create_task(self._dashboard.serve())`.

Para conectar el móvil:
1. Con NEXUS ya corriendo en el PC, pulsa "Remote Control" en el HUD.
2. Aparece un código QR / PIN de 6 caracteres.
3. Desde el navegador del móvil (misma red local), escanea el QR o entra la URL
   `http(s)://<ip-local>:8000` y teclea el PIN.
4. Si hay certificados TLS generados (`config/certs/`), el dashboard sirve HTTPS en
   el puerto 8000 y un alias HTTPS en 8001 para entrada manual de IP.

Si `fastapi` / `uvicorn` / `cryptography` no están instalados, el dashboard se
desactiva solo (log: `[Dashboard] fastapi/uvicorn not installed — dashboard
disabled.`) y **el resto de NEXUS sigue funcionando con normalidad** — confirmado
leyendo `VoiceEngine.run()`, que envuelve el arranque del dashboard en un
`try/except`.

## Ficheros de configuración generados

| Fichero | Contenido | Creado por |
|---|---|---|
| `config/api_keys.json` | Gemini API key, nombre del asistente/usuario, voz, wake word, push-to-talk, hud_style, plugins habilitados, etc. | `memory/config_manager.py`, en el primer guardado |
| `memory/long_term.json` | Hechos guardados por `save_memory`/`recall_memory` | `memory/memory_manager.py`, en el primer `save_memory` |
| `config/certs/jarvis.{key,crt}` | Certificado TLS autofirmado para el dashboard | `dashboard/server.py::_ensure_certs()`, en el primer arranque |

Ninguno de estos ficheros existe en un clon nuevo del repositorio — todos se crean
la primera vez que hacen falta, nunca antes.

## Dependencias opcionales (no instaladas por `setup.py`)

Deliberadamente fuera de `requirements.txt` por tamaño (cientos de MB):
```bash
pip install pandas     # file_processor: análisis de hojas de cálculo/CSV
pip install pydub      # file_processor: metadatos y conversión de audio (necesita ffmpeg)
pip install mediapipe  # mencionado en un comentario para un plugin de conteo de flexiones que NO existe en plugins/
```
