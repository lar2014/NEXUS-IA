# MOBILE.md — Comunicación con dispositivos móviles

## Qué es realmente el "móvil" en este proyecto

No hay una app nativa (Android/iOS) ni un `GestureEngine`. El "cliente móvil" es
una **página web** (`dashboard/static/app.html`, servida por
`dashboard/server.py`) que se abre en el navegador del teléfono. Todo pasa por el
mismo proceso Python que corre en el PC — ver SETUP.md.

## Emparejamiento

1. `DashboardServer.new_key()` genera un PIN de 6 caracteres (alfabeto sin
   caracteres ambiguos: sin `O/I/L/0/1`), válido 600s por defecto.
2. Dos formas de usarlo:
   - **QR**: `GET /auto-login?key=<PIN>` — valida el PIN, crea un token de sesión
     (`secrets.token_urlsafe(32)`) y un `device_token` persistente, y redirige.
   - **Manual**: `POST /login` con el PIN tecleado a mano.
3. A partir de ahí, cada request del móvil lleva `Authorization: Bearer <token>`
   (HTTP) o `?token=<token>` (WebSocket).

## Reconexión automática (dispositivo ya conocido)

`localStorage.jarvis_device_token` (guardado en el propio navegador del móvil) se
usa contra `POST /api/device-login`: si el `device_token` sigue en
`self._device_sessions` (en memoria del proceso — se pierde si NEXUS se reinicia),
el móvil obtiene un token nuevo **sin volver a escanear el QR**. Esto es lo que
hace de "reconexión" un caso real y verificado por lectura de código, no un mero
propósito.

## Canales activos

| Canal | Endpoint | Qué transporta |
|---|---|---|
| Comandos de texto | `POST /api/command` (o `/ws` con `{"type":"command"}`) | Texto cifrado (AES-256-CBC, clave derivada del PIN) o texto plano si no se cifra |
| Voz del móvil | `WS /ws/phone-audio?token=...` | PCM de audio crudo del micrófono del teléfono (16 kHz), **nunca vídeo** |
| Eventos/log en vivo | `WS /ws?token=...` | Difusión (`broadcast`) de lo que ocurre en NEXUS — últimos 50 eventos al conectar, más los que lleguen después |
| Ficheros | `POST /api/upload`, `GET /api/files`, `GET /uploads/{filename}` | Compartir ficheros entre el móvil y el PC (carpeta `~/Downloads/JARVIS Uploads` o similar) |
| Despertar | `POST /api/wake` | Fuerza `wake()` si NEXUS está en modo wake-word dormido |

## Qué pasa con el audio del móvil dentro de NEXUS

`VoiceEngine._relay_phone_audio()` lee de la cola `_phone_audio_queue` del
dashboard con un timeout de 1s:
- Si llega audio → se marca `_phone_active = True` y se inyecta en la sesión de
  Gemini Live (sustituyendo, no sumando, al micrófono del PC mientras dure).
- Si no llega nada durante 1s → `_phone_active = False` y el micrófono del PC
  vuelve a tener el control. **Esto es exactamente lo que hace que "móvil
  desconectado no rompa Nexus"**: no hay ningún estado especial que limpiar, el
  siguiente timeout simplemente devuelve el control al PC.

## Seguridad del canal (detalle ampliado en SECURITY.md)

- AES-256-CBC con clave derivada por SHA-256(PIN + salt fijo) — no hay PBKDF2, la
  propia clave del PIN ya se trata como secreto de un solo uso.
- TLS autofirmado opcional (`config/certs/`), servido en el puerto 8000 (o 8000 y
  un alias 8001 si hay certificados).
- `POST /api/revoke-devices` invalida **todos** los `device_token` a la vez — no
  hay revocación por dispositivo individual.

## Lo que NO existe (verificado leyendo `app.html` y `dashboard/server.py` línea a línea)

- **Cámara del móvil**: `app.html` solo llama a
  `navigator.mediaDevices.getUserMedia({audio: {...}})`. No hay `video: true` en
  ningún sitio del fichero. No hay endpoint para subir fotogramas de cámara.
- **Gestos**: no hay `GestureEngine`, `GestureEvent`, `accelerometer` ni
  `devicemotion`/`deviceorientation` en `app.html`. Ver GESTURES.md.
- **DeviceManager no está enchufado a este servidor**: `nexus_core/device_manager.py`
  existe como registro standalone (`register`/`touch`/`disconnect`/`revoke`/`list_devices`)
  pero nada en `dashboard/server.py` lo llama todavía — el propio módulo lo dice
  explícitamente en su docstring, y la razón dada (no se puede probar un
  emparejamiento real sin PyQt6/micrófono/red en un entorno de pruebas) sigue
  siendo válida aquí, así que no lo he conectado a ciegas en esta pasada.
- **Notificaciones push**: no hay Service Worker ni Web Push en `app.html`.
