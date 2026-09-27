# ARCHITECTURE.md — NEXUS IA 2.0

> Este documento describe únicamente lo que existe en el código de este repositorio
> a fecha de esta auditoría (integración final, fase 2). No describe funcionalidad
> planeada — eso está en las secciones "Pendiente" de cada documento.

## 1. Qué es NEXUS IA 2.0

NEXUS IA 2.0 es una capa de orquestación (`nexus_core/`) construida **encima** de
Mark-LIV, un asistente de voz open-source de un solo proceso (JARVIS-like, de
FatihMakes). Nada de `actions/`, `plugins/`, `memory/`, `core/`, `dashboard/` o
`ui.py` fue reescrito para construir NEXUS: cada módulo de `nexus_core/` **envuelve**
código de Mark-LIV que ya funcionaba, en vez de reimplementarlo.

## 2. Capas del sistema

```
main.py                    ← punto de entrada real (bootstrap de proceso)
  └─ ui.py (JarvisUI)       ← HUD PyQt6: avatar holográfico, logs, paneles
  └─ nexus_core/core.py (NexusCore)   ← orquestador de alto nivel
       ├─ event_bus.py      (EventBus)       — pub/sub interno, sin persistencia
       ├─ security.py       (Security)       — riesgo por tool + gate de confirmación
       ├─ tool_manager.py   (ToolManager)     — registro único de tools (inline+actions+plugins)
       ├─ memory.py         (NexusMemory)     — vista sobre memory/memory_manager.py
       ├─ brain.py          (BrainRouter)     — Fast/Deep/Vision, hoy solo Gemini
       ├─ perception.py     (Perception)      — captura pantalla/cámara + evento VISION_UPDATE
       ├─ agent_manager.py  (AgentManager)    — dev_agent, proactive, background_monitor + 7 "agentes" por permisos
       ├─ planner.py        (Planner)         — descomposición de tareas en pasos (Task/Step)
       ├─ device_manager.py (DeviceManager)   — registro en memoria de dispositivos — NO conectado aún (ver MOBILE.md)
       └─ voice.py          (VoiceEngine)     — el bucle de sesión Gemini Live (antes JarvisLive)
  └─ core/                  ← primitivas de audio/voz/UX, en su mayoría SIN envolver
  └─ actions/                ← 16 tools auto-descubiertas (un módulo = un tool)
  └─ plugins/                 ← tools de terceros, auto-descubiertas (hoy: 0 activos, solo _template.py)
  └─ memory/                  ← almacenamiento: long_term.json + api_keys.json
  └─ dashboard/                ← servidor FastAPI para el panel remoto / móvil
```

## 3. Dos caminos de ejecución, no uno

Es importante no asumir que todo pasa por `NexusCore.handle_text()`. Hay dos rutas
independientes que llegan a los mismos tools:

**A. Turno de voz (Gemini Live)** — el camino principal, probado en producción por
Mark-LIV:

```
micrófono → VoiceEngine._listen_audio → Gemini Live session
          → Gemini decide qué tool llamar (function-calling nativo)
          → VoiceEngine._execute_tool(fc)
              ├─ tools inline (8) → despachadas aquí mismo
              └─ tools de ToolManager (16 actions + plugins) → self.tools.run(name, args, ctx)
          → resultado se devuelve a la sesión Live → TTS nativo de Gemini → altavoz
```

Aquí **no** interviene `BrainRouter.classify()` ni `Planner`: la propia API de
function-calling de Gemini ya decide qué tool usar dentro del turno de voz.

**B. Texto fuera de la sesión de voz (dashboard, futuro API)** —
`NexusCore.handle_text()`:

```
texto (hoy: comandos del dashboard vía /ws) → NexusCore.handle_text()
   → EventBus.publish(USER_MESSAGE)
   → BrainRouter.classify() → intención (CHAT/QUESTION/RESEARCH/.../MEMORY/OTHER)
   → si es MEMORY        → NexusMemory.search()
   → si es tool-intent    → Planner.create_task() → por cada Step → ToolManager.run()
   → si no                → BrainRouter.deep() (respuesta directa)
   → EventBus.publish(AI_RESPONSE)
```

Este segundo camino es real y funcional, pero **no** es el que usa la conversación
por voz normal — sirve para comandos de texto que llegan sin una sesión Live activa.

## 4. Qué NO existe (para que quede explícito, no implícito)

- **Sin GestureEngine ni GestureEvent** — ver GESTURES.md.
- **Sin cámara en el móvil** — el cliente móvil (`dashboard/static/app.html`) solo
  pide `getUserMedia({audio: ...})`; nunca `video`.
- **DeviceManager no está conectado** a `dashboard/server.py` — existe como
  registro standalone, con comentario explícito en el propio código explicando
  por qué no se conectó a ciegas (no se puede probar el emparejamiento real de un
  dispositivo sin hardware).
- **Código huérfano confirmado** (no se importa desde ningún sitio del proceso en
  ejecución): `core/tts.py`, `core/stt.py`, `core/llm_client.py`. Son restos de
  una arquitectura anterior (motor de voz local, previa a adoptar Gemini Live para
  audio nativo). No rompen nada por estar ahí, pero tampoco hacen nada.

## 5. Persistencia (resumen — detalle en MEMORY.md)

Todo el almacenamiento es JSON plano en disco, sin base de datos:
- `memory/long_term.json` — hechos sobre el usuario, gestionado por `memory/memory_manager.py`.
- `config/api_keys.json` — clave de Gemini, nombre del asistente, voz, flags de
  features, config de plugins — gestionado por `memory/config_manager.py`.

## 6. Cómo verifiqué esto

Lectura completa de `nexus_core/*.py`, `memory/*.py`, `dashboard/server.py`,
`core/{confirm,undo,wake_word,echo,hotkey,installer,action_loader,plugin_loader,gemini}.py`,
`actions/screen_processor.py`, cabecera de `actions/dev_agent.py`, `main.py`,
`setup.py`, `dashboard/static/app.html`, más `python3 -m py_compile` (60/60 archivos
sin error de sintaxis) y `python3 -m pyflakes` (sin errores funcionales, solo avisos
cosméticos — ver el informe final). No se ejecutó la aplicación en vivo: este
entorno no tiene pantalla, micrófono, cámara ni una API key real de Gemini — la
misma limitación que el propio código ya reconoce para `DeviceManager`.
