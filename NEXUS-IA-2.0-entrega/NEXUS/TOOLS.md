# TOOLS.md — Herramientas, acciones y plugins

## Tres tipos de tool, un único punto de acceso

`ToolManager` (`nexus_core/tool_manager.py`) es el registro único, pero **no**
ejecuta los tres tipos de la misma forma:

### 1. Tools inline (8) — viven dentro de `VoiceEngine`, no en `ToolManager.run()`

`save_memory`, `recall_memory`, `undo`, `screen_process`, `close_camera`,
`system_status`, `manage_monitor`, `shutdown_jarvis`.

Se quedan inline porque su lógica depende de estado de la sesión en vivo (el
buffer de visión pendiente, si la cámara está en streaming, la secuencia de
apagado) que solo `VoiceEngine` posee. `ToolManager` conoce sus *declaraciones*
(para que aparezcan en la lista de capacidades del modelo y de la UI), pero el
despacho real ocurre en `VoiceEngine._execute_tool()`.

### 2. Actions (16) — auto-descubiertas en `actions/*.py`

Cada fichero expone un `TOOL = {"name": ..., "description": ..., "parameters":
..., "handler": ...}` a nivel de módulo. `core/action_loader.py` las escanea al
arrancar, valida forma y nombre, descarta colisiones, y nunca deja que un fallo
de import tumbe el arranque — se registra el error y se sigue con el resto.

Las 16 confirmadas en este repositorio:

```
browser_control   code_helper       computer_control  computer_settings
desktop_control   dev_agent         file_controller   file_processor
flight_finder     game_updater      open_app          reminder
send_message      weather_report    web_search        youtube_video
```

### 3. Plugins — auto-descubiertos en `plugins/*.py`, formato hermano de actions

Mismo contrato (`PLUGIN = {...}` + `run(parameters, ...)`), pero además pueden
activarse/desactivarse en caliente vía `memory/config_manager.py` sin reiniciar
NEXUS. **Hoy hay 0 plugins activos** — la carpeta `plugins/` solo contiene
`_template.py` (con `_`, así que el loader lo ignora explícitamente).

## Cómo se ejecuta un tool de action/plugin (el camino común)

```
ToolManager.run(name, params, ctx)
  → Security.is_blocked(name)?            → si BLOCK: rechaza, no ejecuta nada
  → Security.requires_confirmation(...)?  → si ASK y no auto-gestionado: pide confirmación (core/confirm.py)
  → ToolManager._dispatch(...)
       → publica TOOL_STARTED
       → ActionRegistry.run() o PluginRegistry.run() (nunca ambos)
       → publica TOOL_FINISHED (con tiempo transcurrido)
```

Tanto `ActionRegistry.run()` como `PluginRegistry.run()` envuelven la llamada al
handler en `try/except Exception` — un action o plugin que lanza una excepción
**nunca** tira el proceso, devuelve un string de error que se lee en voz alta.
Esto está verificado leyendo el código, no ejecutándolo con hardware real.

## Aislamiento de fallos — por qué un tool roto no rompe NEXUS

Hay **tres** capas independientes de aislamiento, no una:
1. `core/action_loader.py` / `core/plugin_loader.py`: un fichero que no importa,
   o cuyo `TOOL`/`PLUGIN` está mal formado, se descarta en el descubrimiento —
   nunca aborta el escaneo de los demás ficheros.
2. `ActionRegistry.run()` / `PluginRegistry.run()`: capturan cualquier excepción
   del `handler`/`run()` en tiempo de ejecución.
3. `VoiceEngine._execute_tool()`: el `try/except` que envuelve *toda* la
   invocación (inline y no-inline) y llama a `self.speak_error(...)` si algo se
   escapa de las dos capas anteriores.

## AgentManager — 7 "agentes" como agrupación de permisos, no como lógica nueva

`PersonalAgent`, `ResearchAgent`, `ComputerAgent`, `CodingAgent`, `BrowserAgent`,
`FileAgent`, `PlanningAgent` son particiones del mismo conjunto de 24 tools — cada
tool pertenece exactamente a un agente ("no hagas que todos puedan hacer todo").
`AgentManager.run_as(agent, tool, ...)` rechaza un tool que no esté en el
conjunto del agente que lo invoca. **`run_as()` existe y está probado en su
forma, pero nada en el código lo llama todavía** — es una interfaz lista para un
futuro llamador (por ejemplo, un Planner que asigne pasos a agentes concretos),
no una ruta activa hoy.

Tres tools quedan deliberadamente sin agente: `screen_process` / `close_camera`
(estado de sesión en vivo) y `shutdown_jarvis` (apaga el propio asistente, no es
una tarea delegable).

## Planner — descomposición en pasos, tampoco en el camino de voz

`Planner.plan()` pide a `BrainRouter.deep_json()` una lista de pasos, cada uno
con el nombre de un tool real (o `"none"` si no hace falta tool) — y si el
modelo inventa un nombre de tool que no existe, se sustituye por `"none"` en vez
de fallar. `Task`/`Step` (con estados PENDING/RUNNING/DONE/FAILED) dan
seguimiento a la ejecución. Solo lo usa `NexusCore._run_task()`, llamado desde
`handle_text()` — es decir, comandos de texto fuera de la sesión de voz (hoy:
los que llegan por el dashboard). La conversación por voz normal no pasa por
aquí porque el function-calling nativo de Gemini ya cumple ese papel dentro de
un turno de voz.

## Comportamiento no bloqueante (`scheduling`)

Un tool puede declarar `behavior: "NON_BLOCKING"` y `scheduling` (`WHEN_IDLE` /
`SILENT` / `INTERRUPT`) para que su resultado no interrumpa una frase que el
asistente ya está diciendo. `ToolManager.scheduling(name)` consulta esto tanto en
actions como en plugins.
