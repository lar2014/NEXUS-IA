# SECURITY.md — Modelo de seguridad

## Dos mecanismos distintos, con papeles distintos

`core/confirm.py` y `core/undo.py` resuelven problemas opuestos y **no se
solapan por diseño**:

- **`confirm.py`** — solo para lo genuinamente irreversible (apagar el equipo,
  reiniciar, cambiar de WiFi). El token de confirmación lo emite la **interfaz**,
  nunca el modelo: un `run: Callable` queda aparcado hasta que el usuario pulsa
  CONFIRM en el HUD; el modelo no puede fabricar ese "sí" enviando un parámetro
  `confirmed=yes`. Expira a los 90s.
- **`undo.py`** — para todo lo reversible: actuar ya y guardar cómo deshacerlo
  (pila LIFO, máx. 10 entradas). La alternativa de preguntar antes de cada acción
  se descarta explícitamente en el propio código por mala UX.

## Niveles de riesgo por tool (`nexus_core/security.py`)

`LOW` / `MEDIUM` / `HIGH` (+ `SAFE`, que no corresponde a ningún tool — es para un
turno que no llama a ningún tool). Un tool sin nivel explícito ni entrada en la
tabla **cae en MEDIUM por defecto, nunca en LOW** — para que nada quede
silenciosamente "de confianza" por omisión.

| Política por nivel (por defecto) | AUTO | ASK | BLOCK |
|---|---|---|---|
| SAFE / LOW / MEDIUM | ✔ | | |
| HIGH | | ✔ | |

Configurable en caliente con `Security.set_policy(nivel, política)` — incluye
`BLOCK`, que Phase 1 (antes de esta capa) no podía expresar en absoluto: un tool
en BLOCK se rechaza en `ToolManager.run()` **antes** de llegar siquiera al gate de
confirmación.

`computer_settings` está marcado como `_SELF_GATED`: ya implementa su propia
confirmación con `core/confirm.py` para apagar/reiniciar/wifi, así que
`ToolManager` no le añade una segunda confirmación por encima.

Una decisión de diseño dejada explícita en el propio código, no oculta:
`file_controller.delete_file` se clasifica `MEDIUM`, no `HIGH`, porque el borrado
pasa por `send2trash` (recuperable) y registra una entrada de `undo` — pero el
propio comentario dice "Ángel, si quieres que el borrado de ficheros pida
confirmación siempre, dímelo y lo paso a `_HIGH_RISK`". Lo dejo tal cual está,
sin decidir por ti.

## AgentManager como capa adicional de permisos

Los 24 tools se reparten entre 7 "agentes" (ver TOOLS.md) y cada uno solo puede
usar los suyos — pero esto solo se aplica si algo llama a `run_as()`, y **hoy
nada lo llama**. Es una barrera lista, no una barrera activa.

## Seguridad del canal móvil/dashboard

- Emparejamiento por PIN de 6 caracteres (600s de validez, un solo uso) o QR.
- AES-256-CBC con clave derivada de SHA-256(PIN + salt fijo) para los comandos
  cifrados desde el móvil.
- Tokens de sesión (`secrets.token_urlsafe(32)`) — no cookies; van en el header
  `Authorization` o como query param solo donde el navegador no permite headers
  personalizados (descarga de ficheros).
- TLS autofirmado opcional, generado localmente la primera vez
  (`config/certs/`) — nunca se distribuye una clave privada en el repositorio.
- `POST /api/revoke-devices` invalida **todos** los dispositivos emparejados de
  golpe — no hay revocación selectiva por dispositivo.

## Lo que NO hay (para que no se dé por hecho)

- **Sin cifrado en reposo**: `memory/long_term.json` y `config/api_keys.json`
  (incluida la API key de Gemini) están en texto plano en disco. Cualquier
  proceso con acceso al sistema de ficheros los lee sin más.
- **Sin control de permisos por dispositivo**: al no estar conectado
  `DeviceManager`, un dispositivo emparejado tiene acceso a todo lo que el
  dashboard expone — no hay "este móvil solo puede X".
- **Sin modelo de permisos de gestos/cámara móvil**: no aplica, porque esa
  funcionalidad no existe (ver GESTURES.md) — no hay nada que asegurar todavía.
- **Sin límite de intentos en el PIN de login**: `POST /login` no lleva
  rate-limiting visible en el código — un PIN de 6 caracteres válido 600s es
  fuerza-bruteable en ese tiempo si alguien tiene acceso a la red local. No es un
  fallo introducido por esta auditoría; es el estado del código tal cual estaba.
