# GESTURES.md — Estado de la detección de gestos

## Resultado de la auditoría, sin rodeos

**No existe ninguna funcionalidad de gestos en este código.** Ni parcial, ni
deshabilitada, ni "casi lista". Lo digo así de claro porque el pipeline que se
pedía verificar era:

```
MÓVIL → cámara → gesto → GestureEngine → GestureEvent → NexusCore → Permission → Tool → resultado → móvil
```

De esos nueve pasos, solo tres tienen código real: **NexusCore**, **Permission**
(el módulo `nexus_core/security.py`, que gestiona riesgo/confirmación de tools —
no permisos de dispositivo) y **Tool** (`ToolManager`). Los otros seis — cámara
del móvil, detección de gesto, `GestureEngine`, `GestureEvent`, y el camino de
vuelta al móvil con el resultado de un gesto — no existen en ninguna forma.

No he construido nada de esto en esta pasada porque se pidió explícitamente
**no añadir funcionalidades nuevas importantes** y estabilizar lo ya construido —
construir un `GestureEngine` desde cero sería justo lo contrario.

## Lo único relacionado que hay: dos nombres reservados

En `nexus_core/event_bus.py`:

```python
GESTURE_DETECTED = "GESTURE_DETECTED"   # not produced yet — no gesture
                                         # input exists in this codebase
CAMERA_FRAME = "CAMERA_FRAME"           # reserved for a future continuous
                                         # mobile/Nexus Room camera feed
```

Son constantes de tipo de evento para el bus interno (`EventBus`). Ningún módulo
del proyecto llama a `bus.publish(GESTURE_DETECTED, ...)` ni a
`bus.publish(CAMERA_FRAME, ...)` — confirmado con:

```bash
grep -rn "GESTURE_DETECTED\|CAMERA_FRAME" --include="*.py" .
```

que solo encuentra la línea donde se **definen**, no donde se **usan**. Existen
para que, el día que alguien construya la detección de gestos, no tenga que tomar
una decisión de nombrado a mitad de esa implementación — nada más.

## Lo que sí existe, y no debe confundirse con "gestos"

- `ui.py` tiene `mousePressEvent` / `mouseMoveEvent` / `dragEnterEvent` — son
  interacción estándar de ventana de escritorio con PyQt6 (arrastrar la ventana sin
  bordes, soltar un fichero para subirlo). No tienen relación con gestos captados
  por cámara o con el cuerpo del usuario.
- La cámara del **PC** (no del móvil) sí funciona, vía `actions/screen_processor.py`
  → `nexus_core/perception.py` → tool inline `screen_process` — pero es una
  fotografía puntual bajo petición de voz ("mira mi cámara"), no un flujo continuo,
  y no hay ningún análisis de gestos sobre esa imagen — solo se envía al modelo de
  Gemini para que describa lo que ve si el usuario lo pide.
- `requirements.txt` menciona `mediapipe` en un comentario, como dependencia
  opcional de un plugin de "conteo de flexiones" (`pushup_counter`) — pero ese
  plugin **no existe** en `plugins/` (solo está `_template.py`). Es una nota para
  una idea futura, no código.

## Qué haría falta para construir esto (fuera de alcance de esta pasada)

Si en el futuro se decide implementarlo, la costura ya está pensada:
1. En el móvil: `getUserMedia({video: true})` + envío de fotogramas (o
   landmarks ya procesados con una librería tipo MediaPipe Tasks *en el propio
   navegador*, que es más barato que subir vídeo crudo).
2. Un endpoint nuevo en `dashboard/server.py` (WebSocket, como `/ws/phone-audio`
   pero para vídeo o landmarks).
3. Un `GestureEngine` que traduzca esos datos en gestos discretos y publique
   `bus.publish(ev.GESTURE_DETECTED, gesture=..., device_id=...)`.
4. Un suscriptor en `NexusCore` que traduzca cada `GESTURE_DETECTED` en una
   llamada a `ToolManager.run(...)`, pasando primero por `Security` igual que
   cualquier otro tool.

Ninguno de estos cuatro puntos está construido. No los he construido yo tampoco,
por la razón indicada arriba.
