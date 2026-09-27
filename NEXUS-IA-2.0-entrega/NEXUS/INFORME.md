# INFORME FINAL — Integración NEXUS IA 2.0 (Fase 2)

## Metodología y sus límites

Auditoría **estática y de lectura de código**: `python3 -m py_compile` sobre los
60 ficheros `.py` del proyecto, `python3 -m pyflakes` sobre todo el árbol, y
lectura línea a línea de `nexus_core/*`, `memory/*`, `dashboard/server.py`,
`core/{confirm,undo,wake_word,echo,hotkey,installer,action_loader,plugin_loader,gemini}.py`,
`actions/screen_processor.py`, cabecera de `actions/dev_agent.py`, `main.py`,
`setup.py`, `config/*`, `dashboard/static/app.html`.

**No se ejecutó la aplicación en vivo.** Este entorno no tiene pantalla (PyQt6
necesita una), micrófono, cámara, ni una API key real de Gemini — la misma
limitación que el propio código ya documentaba para justificar por qué
`DeviceManager` no se conectó a ciegas. Todo lo marcado como "verificado" abajo
lo es por lectura y trazado de código, no por ejecución real; lo marco así en
cada punto en vez de dar a entender lo contrario.

---

## Prueba end-to-end nº 1 — turno de voz

```
USUARIO → voz → Nexus → interpretación → planner → tool → resultado → memoria → respuesta por voz
```

Trazado en el código, paso a paso:

1. `sounddevice` captura el micrófono en `VoiceEngine._listen_audio()`.
2. El audio va a la sesión de **Gemini Live** (`self.session`), que decide con su
   propio function-calling qué tool llamar — **no** pasa por `Planner` ni por
   `BrainRouter.classify()`: la sesión de voz ya tiene ese papel cubierto por el
   modelo, según explica el propio `nexus_core/core.py`.
3. `VoiceEngine._execute_tool(fc)` despacha: 8 tools inline aquí mismo, el resto
   vía `ToolManager.run()` (que aplica `Security` antes de ejecutar).
4. El resultado (string) vuelve a la sesión Live como `FunctionResponse`.
5. Memoria: si el tool fue `save_memory`, se escribe en `long_term.json` vía
   `NexusMemory.update()`; en cualquier caso, el turno se añade a
   `self.memory.short_term` (RAM) y al cerrar la sesión se resume a
   `episodic`/`sessions` vía `_save_session_summary()`.
6. La respuesta hablada sale por el **audio nativo de Gemini Live** (no hay una
   TTS local en este camino — `core/tts.py` está huérfano, ver más abajo).

**Verificado por código: sí, el camino existe completo y coherente.**
**No verificado en vivo**: no hay forma de confirmar en este entorno que el audio
realmente suena, que la latencia es aceptable, o que el reconocimiento de voz de
Gemini Live interpreta correctamente — eso requiere hardware real.

## Prueba end-to-end nº 2 — móvil / gesto

```
MÓVIL → cámara → gesto → GestureEngine → GestureEvent → NexusCore → Permission → Tool → resultado → móvil
```

**No se puede trazar de extremo a extremo porque 6 de los 9 pasos no existen en
el código.** Lo que sí existe:

- `MÓVIL` → sí, vía el dashboard web (`dashboard/server.py` + `app.html`).
- `cámara` → **no**. `app.html` solo pide `getUserMedia({audio:...})`.
- `gesto` / `GestureEngine` / `GestureEvent` → **no existen en ninguna forma**
  (ver GESTURES.md — solo dos constantes de evento reservadas, sin publicador).
- `NexusCore` → sí, existe y es alcanzable desde el móvil, pero solo para
  **texto** (`handle_text()`, alimentado hoy por comandos del dashboard).
- `Permission` → interpreto que se refiere a `nexus_core/security.py`
  (`Security`) — existe y se aplica a cualquier tool, venga de donde venga.
- `Tool` → sí, mismo `ToolManager` que en la prueba nº 1.
- `resultado → móvil` → parcialmente: el resultado de un comando de texto sí
  vuelve al móvil vía el broadcast de `/ws` (eventos `AI_RESPONSE` etc.), pero no
  hay un "resultado de un gesto" porque no hay gestos.

**Conclusión honesta**: esta prueba no se puede dar por pasada ni por fallida —
la funcionalidad que prueba no está construida. No la he simulado ni he
fabricado un resultado positivo.

---

## Comprobaciones de resiliencia pedidas

| Comprobación | Resultado | Cómo se verificó |
|---|---|---|
| Cámara (PC) desconectada no rompe Nexus | **Confirmado por código** | `actions/screen_processor.py::_capture_camera()` lanza `RuntimeError` si no abre o no da frame; `_execute_tool` lo captura en su `try/except` y responde con un error hablado, sin caer el proceso |
| Móvil desconectado no rompe Nexus | **Confirmado por código** | `VoiceEngine._relay_phone_audio()`: tras 1s sin audio del móvil, `_phone_active=False` y el micrófono del PC recupera el control automáticamente — sin estado que limpiar |
| API externa (Gemini) no disponible no rompe Nexus | **Confirmado por código** | `core/gemini.py::call()` devuelve `None` (nunca lanza) si no hay key o si toda la escalera de modelos falla; `BrainRouter` propaga ese `default=...` en vez de romper; `VoiceEngine.run()` además tiene manejo específico de "API key inválida" y de errores de red con backoff exponencial |
| Generación de imágenes no configurada no rompe Nexus | **No aplica — la funcionalidad no existe** | Búsqueda exhaustiva (`grep -rniE "image.?generat\|generate.?image"`) no encuentra ningún tool ni acción de generación de imágenes en el proyecto. No hay nada que "no romper" porque no hay nada construido |
| Creación de apps (dev_agent) no configurada no rompe Nexus | **Confirmado por código** | `actions/dev_agent.py::_get_api_key()` puede lanzar si falta `config/api_keys.json`, pero **toda** invocación de una action pasa por `ActionRegistry.run()`, que envuelve el handler en `try/except Exception` y devuelve un string de error — nunca tumba el proceso |

---

## Errores encontrados

No se encontró **ningún error funcional**. Lo que sí encontré, por orden de
relevancia:

1. **Tres módulos huérfanos** — `core/tts.py`, `core/stt.py`, `core/llm_client.py`
   no los importa nada en el proceso en ejecución (confirmado con `grep -rn`
   contra todo el árbol). Son restos de una arquitectura anterior a Gemini Live.
   No rompen nada por estar ahí; tampoco aportan nada estando ahí.
2. **`DeviceManager` sin conectar** — existe, está bien escrito, pero
   `dashboard/server.py` no lo usa. Ya estaba documentado como decisión
   deliberada en el propio código (no se podía probar en un entorno sin
   hardware) — la misma razón aplica aquí, así que no lo he conectado a ciegas.
3. **Tres entradas muertas en la tabla de riesgo** — `security.py::_ACTION_RISK`
   incluye `"system_monitor"`, `"background_monitor"` y `"proactive"`, pero
   ninguno de esos tres módulos expone un `TOOL` dict, así que nunca son
   tools invocables por nombre y esas entradas nunca se consultan. Inofensivo,
   pero es ruido en la tabla.
4. **Avisos cosméticos de `pyflakes`** (≈35 en todo el proyecto, casi todos en
   `ui.py` y en `actions/*.py` preexistentes de Mark-LIV): imports sin usar,
   f-strings sin placeholder, una variable local sin usar en `core/llm_client.py`
   y otra en `actions/code_helper.py`. Ninguno afecta al comportamiento.

## Errores solucionados

**Ninguno — porque no hacía falta arreglar nada funcional.** No he tocado
código de producción en esta pasada: el aislamiento de fallos ya existente
(3 capas, ver TOOLS.md) es sólido y está verificado en los cinco puntos de la
tabla de arriba. Cambiar código sin poder probarlo en vivo (sin PyQt6, micro,
cámara ni key real) sería el mismo riesgo que el propio proyecto ya evitó
deliberadamente con `DeviceManager` — así que apliqué el mismo criterio: no
tocar lo que no puedo verificar que sigue funcionando después del cambio.

## Funcionalidades verificadas (por lectura/trazado de código)

Arranque del sistema · descubrimiento de 24 tools (16 actions + 8 inline) ·
0 plugins activos (mecanismo de plugins probado con `_template.py`) ·
wake word (ciclo de vida completo: instalación, detección, sleep/wake) ·
conversación por voz (turno completo, ver prueba nº 1) · memoria (lectura,
escritura, recorte por límite, recall léxico) · confirmaciones (`confirm.py`,
token emitido por la UI) · undo (pila de 10, LIFO) · dashboard (emparejamiento
PIN/QR, comandos cifrados, subida/descarga de ficheros) · reconexión (backoff
exponencial en `VoiceEngine.run()`, reconexión de dispositivo vía
`device_token` en el dashboard) · gestión de errores (3 capas de aislamiento,
ver tabla de resiliencia) · almacenamiento (dos JSON, sin cifrado, con guarda
anti-crecimiento).

## Funcionalidades pendientes / no implementadas

Gestos (0%, ver GESTURES.md) · cámara del móvil (0%) · `DeviceManager` sin
conectar al dashboard · `AgentManager.run_as()` sin ningún llamador todavía ·
`Planner`/`handle_text()` sin usar desde el camino de voz (solo desde texto del
dashboard) · limpieza de los 3 módulos huérfanos (decisión pendiente: borrarlos
o cablearlos a un proveedor de LLM local) · rate-limiting del PIN de login del
dashboard · cifrado en reposo de `long_term.json`/`api_keys.json`.

---

## Comandos exactos

**Arrancar Nexus:**
```bash
python setup.py     # una sola vez — instala dependencias
python main.py       # cada arranque — pide la API key de Gemini la primera vez
```

**Arrancar el "cliente móvil":** no existe un comando separado — es la misma
`python main.py`, que levanta el dashboard automáticamente. Desde el móvil:
pulsar "Remote Control" en el HUD del PC, escanear el QR (o teclear el PIN) en
el navegador del teléfono, misma red local.
