# NEXUS_CLOUD_ARCHITECTURE.md — De NEXUS IA 2.0 a Nexus Cloud + Nexus Agent

## 0. Cómo leer este documento

Por cada pieza de la visión (Nexus Cloud + Nexus Agent), digo tres cosas:
**qué ya existe y se puede reutilizar tal cual**, **qué existe pero hay que
adaptar**, y **qué es genuinamente nuevo y no hay nada parecido todavía**. Esta
distinción es el trabajo más importante de este documento — la especificación
pide explícitamente "no reemplaces funcionalidades simplemente porque exista una
forma diferente de hacerlo", así que antes de proponer nada nuevo compruebo si
ya existe.

## 1. El giro conceptual: qué es el Agent que ya tienes

La pieza que más cambia de sitio, conceptualmente, es esta: **el proyecto NEXUS
IA 2.0 que ya tienes NO se convierte en "Nexus Cloud" — se convierte en la
primera implementación de Nexus Agent (Windows).**

Esto no es una degradación — es exactamente el hueco que la especificación dice
que falta ("si actualmente no existe Agent, prepara la arquitectura..."). Ya
existe, y es sorprendentemente completo para ese papel:

| Pieza que pide "Nexus Agent" (spec §2) | Qué ya tienes | Estado |
|---|---|---|
| "recibe acciones autorizadas desde Nexus" | `ToolManager.run()` + `nexus_core/actions_schema.py` (nuevo, esta pasada) | ✅ listo para recibir, falta el transporte de red hacia la nube |
| "ejecuta acciones localmente" | Los 24 tools (16 actions + 8 inline) | ✅ ya funciona |
| "devuelve el resultado a Nexus" | `dashboard/server.py::broadcast()` (hoy solo LAN) | 🟡 el patrón existe, falta apuntarlo a la nube en vez de al WebSocket local |
| "anuncia qué capacidades soporta" | `nexus_core/actions_schema.py::capabilities_for()` (nuevo, esta pasada) | ✅ genera exactamente el JSON de la spec §3 |

## 2. Mapeo pieza por pieza de la visión

### 2.1 Multiusuario (spec §5) — 🔴 genuinamente nuevo
Hoy, `memory/long_term.json` y `config/api_keys.json` son **de la instalación**,
no de un usuario — no hay concepto de "usuario" en el Agent en absoluto. Esto es
correcto para un Agent (un Agent vive en un dispositivo de una persona), pero
significa que el multiusuario **tiene que vivir en Nexus Cloud**, no en el
Agent. `cloud/schema.sql` ya lo modela: cada tabla tiene `user_id` con Row Level
Security, que es la garantía real (a nivel de base de datos, no solo de
aplicación) de que "nunca una petición del usuario A se ejecute en el
dispositivo del usuario B" — el aislamiento no depende de que el código de la
aplicación nunca tenga un bug, depende de que Postgres rechace la fila aunque lo
tuviera.

### 2.2 Seguridad (spec §13) — 🟢 ya muy avanzado en el Agent, 🔴 nuevo en Cloud
En el Agent, revisé esto a fondo en la auditoría anterior (ver `SECURITY.md`):
niveles de riesgo por tool, confirmación que el modelo no puede forjar,
undo, sin secretos hardcodeados. Lo único nuevo que añade esta visión es la capa
de **permiso por dispositivo** (spec §4/§6) — que ya añadí a `DeviceManager`
esta pasada (`permissions`, `set_permission()`, `permission_for()`) — y la
gestión de secretos **en la nube** (`provider_configs.api_key_vault_id` en
`cloud/schema.sql`, vía Supabase Vault, nunca en texto plano).

### 2.3 Proveedores de IA (spec §8) — 🟡 el seam existe, la implementación es parcial y hay que ser honesto con el límite real
`nexus_core/brain.py` (`BrainRouter`) ya es exactamente la capa de abstracción
que pide la spec — **pero hoy solo tiene un proveedor conectado (Gemini)**, y
esto **por diseño**, según dice su propio docstring: "la spec es explícita en
que Nexus debe funcionar con un solo proveedor configurado". Extender
`BrainRouter.fast/deep/deep_json` a Claude/OpenAI/OpenRouter para tareas de
texto (clasificación, planificación) es una extensión razonable y de bajo
riesgo — el patrón de "ladder con fallback y timeout" ya está ahí.

Lo que **no** puedo prometer resolver con el mismo bajo riesgo: la
**conversación de voz en tiempo real** (`nexus_core/voice.py`) está construida
sobre la API de **Gemini Live** específicamente — audio nativo bidireccional,
function-calling dentro del propio stream. No existe hoy un estándar
equivalente entre proveedores (OpenAI, Anthropic y Gemini no exponen la misma
forma de "sesión de voz en vivo"). Hacer la voz multiproveedor sería una
reescritura real de `voice.py`, no una extensión — lo digo aquí en vez de
fingir que es trivial.

### 2.4 Memoria (spec §9) — 🟢 el modelo ya está bien separado, falta trasladarlo
Ya tenías, sin que esta visión lo pidiera, la separación conceptual exacta que
pide la spec: `short_term` (RAM, de la conversación) vs `episodic`/`identity`/
etc. (persistente) vs `procedural` (del sistema) — ver `MEMORY.md`. Lo que hace
falta es mover el *almacenamiento* de "un JSON por instalación" a "una fila en
`memory_entries` por usuario" (`cloud/schema.sql`) — el modelo conceptual no
cambia, cambia dónde vive.

### 2.5 Dispositivos y vinculación (spec §6-7) — 🟢 base sólida, extendida esta pasada
`nexus_core/device_manager.py` ya tenía el registro (`register`/`touch`/
`disconnect`/`revoke`/`list_devices`) y el campo `capabilities`. Esta pasada
añadí lo que faltaba para la spec: `permissions` por dispositivo,
`linked_at`, y `generate_pairing_code()` (formato `7F4-K92`, mismo criterio de
alfabeto sin ambigüedades que ya usa `dashboard/server.py::_KEY_CHARS`). El
propio `dashboard/server.py` ya resuelve, para LAN, casi todo el flujo de
vinculación que pide la spec §7 (PIN/QR → sesión → reconexión por
`device_token`) — es el mismo patrón que `cloud/schema.sql` traslada a
`devices.pairing_code` para la nube.

### 2.6 Sistema de acciones (spec §3) — 🟢 construido esta pasada
`nexus_core/actions_schema.py` (nuevo). Traduce el JSON estructurado
`{"action": "OPEN_APP", "target": "whatsapp", "device_id": "..."}` a
`ToolManager.run(...)`, reutilizando el 100% del aislamiento de fallos y del
gating de `Security` que ya existía — no crea un segundo camino de ejecución
paralelo. De los 13 `ACTION_TYPES` de la spec, **12 ya tienen un tool real
detrás** en este Agent (verificado contra el `parameters` real de cada tool,
no supuesto — corregí tres mapeos durante las pruebas: `SEND_MESSAGE`,
`file_controller` y `LOCK_DEVICE`, que sí existe vía `computer_settings`,
acción `lock_screen`). Solo `READ_NOTIFICATION` no tiene tool equivalente hoy.

### 2.7 Permisos (spec §4) — 🟢 ya existía casi todo el vocabulario
Aquí me llevé una sorpresa buena al revisar: `nexus_core/security.py` **ya**
tenía `LEVEL_ALIASES` mapeando `SAFE/LOW_RISK/SENSITIVE/DANGEROUS` a políticas
`AUTO/ASK/BLOCK` — que es, con otro nombre, exactamente PERMITIDO/REQUIERE
CONFIRMACIÓN/BLOQUEADO de la spec §4. No lo he tocado porque ya cumple. Lo que
añadí es el eje que faltaba: el permiso **por dispositivo concreto**
(`DeviceManager.permissions`), que puede estrechar (nunca ampliar) lo que
`Security` ya permitiría por tipo de tool.

### 2.8 Voz / wake word (spec §12) — 🟢 ya preparado, sin tocar
El wake word local (`core/wake_word.py`) ya existe, es opt-in, y no bloquea
nada si está desactivado — cero cambios necesarios para "no imposibilitar"
añadirlo, porque ya está añadido.

### 2.9 Plataformas adicionales: Android / iOS (spec §2, §11) — 🔴 genuinamente nuevo, y el punto más grande de honestidad de este documento
El "móvil" que existe hoy (ver `MOBILE.md`) es una **página web** que solo
retransmite el micrófono — no es un Agent, no ejecuta acciones, no anuncia
capacidades. Un Nexus Agent real para Android o iOS es una **app nativa nueva**
(o al menos un servicio en segundo plano con permisos de sistema) que no existe
en ninguna forma en este repositorio, y no es algo que se pueda "preparar sin
implementar" del mismo modo que el resto — necesita su propio proyecto, en su
propio lenguaje (Kotlin/Swift, o React Native/Flutter si se quiere compartir
código). Lo que sí queda listo desde este repositorio es el contrato que ese
futuro Agent tendría que hablar: el mismo JSON de `capabilities_for()` y el
mismo formato `Action` de `nexus_core/actions_schema.py` — son independientes
del lenguaje en el que se implemente el Agent.

## 3. Diagrama del flujo completo objetivo

```
Usuario: "Hey Nexus, abre WhatsApp"
   │
   ▼
Nexus Agent (el dispositivo que escucha — hoy: el PC con NEXUS IA 2.0)
   │  interpreta con Gemini Live (voice.py) — igual que hoy
   ▼
¿La acción es para ESTE dispositivo o para otro vinculado a la misma cuenta?
   │
   ├─ Para este dispositivo → nexus_core/actions_schema.to_tool_call()
   │                          → ToolManager.run() (Security ya aplica)
   │                          → resultado hablado, igual que hoy
   │
   └─ Para OTRO dispositivo → (🔴 nuevo) petición a Nexus Cloud
                               → Cloud resuelve qué Agent es "whatsapp en el
                                 Android de Ángel" (tabla devices, RLS)
                               → Cloud envía la Action a ESE Agent (WebSocket)
                               → ese Agent la ejecuta, devuelve resultado
                               → Cloud lo registra en actions_log
                               → Nexus Agent original lo dice en voz alta
```

Hoy, la app solo cubre la rama izquierda (dispositivo local). La rama derecha
es la parte de Nexus Cloud que todavía no existe como servicio desplegado.

## 4. Qué NO he tocado, y por qué

`voice.py`, `ui.py`, `dashboard/server.py` y los 24 tools existentes — **cero
cambios**. Todo lo nuevo de esta pasada son ficheros añadidos
(`nexus_core/actions_schema.py`, `cloud/`) o extensiones aditivas a un módulo
que ya estaba confirmado como no conectado a nada (`device_manager.py`) — el
mismo criterio de "no tocar lo que no puedo verificar que sigue funcionando
después" que ya apliqué en la auditoría anterior.
