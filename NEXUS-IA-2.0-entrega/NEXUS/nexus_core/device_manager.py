"""
nexus_core/device_manager.py — DeviceManager (NEXUS spec, §1 core layout).

Genuinely NEW: Mark-LIV's dashboard (dashboard/server.py) tracks connected
WebSocket clients by a bare token, with no name, type or capability
attached to them — there was no concept of "a device" to manage, only "a
connection". This module adds that concept as a standalone, in-memory
registry.

Deliberately NOT wired into dashboard/server.py in this pass. That file is
884 lines carrying real security logic (AES-256-CBC over TLS, the firewall
auto-elevation flow, the phone-audio WebSocket) that this sandbox cannot
exercise end-to-end (no PyQt6/microphone/network access to test a live
pairing). Wiring DeviceManager in blind — guessing at the right point to
call `register()` inside a file this sensitive — is a worse risk than
leaving it disconnected and flagging it clearly here and in the final
report. The seam is ready (`register`, `touch`, `list_devices`,
`revoke`); connecting dashboard/server.py's `/ws` and `/ws/phone-audio`
handlers to it is a follow-up step, not done today.
"""
from __future__ import annotations

import secrets
import string
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from nexus_core import event_bus as ev

# ── PROMPT 3 (evolución Nexus Cloud/Agent), §4 y §6-7 ───────────────────────
# Vocabulario EXACTO pedido en la especificación de permisos (sección 4). No
# reinventa nada: es el mismo vocabulario que nexus_core/security.py ya expone
# como LEVEL_ALIASES (SAFE/LOW_RISK/SENSITIVE/DANGEROUS -> AUTO/ASK/BLOCK) para
# el riesgo POR TOOL. Esto añade el eje que faltaba: el permiso POR DISPOSITIVO,
# que puede estrechar (nunca ampliar) lo que security.py ya permitiría — un
# dispositivo puede tener bloqueada una acción que, por su nivel de riesgo,
# normalmente se ejecutaría sola.
PERM_ALLOWED       = "PERMITIDO"
PERM_CONFIRM       = "REQUIERE_CONFIRMACION"
PERM_BLOCKED       = "BLOQUEADO"
_DEVICE_PERMS = (PERM_ALLOWED, PERM_CONFIRM, PERM_BLOCKED)

# Alfabeto sin caracteres ambiguos — mismo criterio que
# dashboard/server.py::_KEY_CHARS (sin 0/O/1/I/L), para que un código leído en
# voz alta o escrito a mano no se confunda. Formato "7F4-K92" (spec §7).
_CODE_CHARS = [c for c in (string.ascii_uppercase + string.digits)
               if c not in ("O", "I", "L", "0", "1")]


@dataclass
class Device:
    device_id: str
    name: str
    type: str                       # "pc" | "mobile" | "tablet" | "nexus_room" | ...
    capabilities: dict = field(default_factory=dict)
    # Permiso por ACTION_TYPE para ESTE dispositivo (ver nexus_core/actions_schema.py).
    # Ausente = se usa la política por defecto de Security (riesgo del tool);
    # presente = ESTE dispositivo concreto lo tiene restringido/permitido de
    # forma explícita, por encima de esa política general.
    permissions: dict = field(default_factory=dict)
    connected: bool = True
    last_seen: float = field(default_factory=time.time)
    linked_at: float = field(default_factory=time.time)   # spec §6: "fecha de vinculación"


class DeviceManager:
    def __init__(self, bus: Optional["ev.EventBus"] = None) -> None:
        self._bus = bus
        self._devices: dict[str, Device] = {}

    def register(self, name: str, type: str, capabilities: Optional[dict] = None,
                 device_id: Optional[str] = None) -> Device:
        device_id = device_id or uuid.uuid4().hex[:12]
        dev = Device(device_id=device_id, name=name, type=type,
                     capabilities=capabilities or {})
        self._devices[device_id] = dev
        if self._bus:
            self._bus.publish(ev.DEVICE_CONNECTED, device_id=device_id, name=name, type=type)
        return dev

    # -- vinculación (spec §7): "Instalar Nexus Agent -> código -> vincular" --
    @staticmethod
    def generate_pairing_code() -> str:
        """Código de un solo uso, formato XXX-XXX (p. ej. '7F4-K92'). Generarlo
        es responsabilidad de este módulo; VALIDARLO y darle expiración (como
        ya hace DashboardServer.new_key() con su PIN de 600s) es trabajo de
        quien lo use — hoy nadie, ver el docstring del módulo."""
        chars = [secrets.choice(_CODE_CHARS) for _ in range(6)]
        return "".join(chars[:3]) + "-" + "".join(chars[3:])

    # -- permisos por dispositivo (spec §4 y §6) -----------------------------
    def set_permission(self, device_id: str, action_type: str, level: str) -> None:
        """Fija el permiso de UN action_type para UN dispositivo concreto.
        `level` debe ser uno de PERM_ALLOWED / PERM_CONFIRM / PERM_BLOCKED."""
        level = level.strip().upper()
        if level not in _DEVICE_PERMS:
            raise ValueError(f"unknown permission level: {level!r} (want one of {_DEVICE_PERMS})")
        dev = self._devices.get(device_id)
        if dev is None:
            raise KeyError(f"unknown device_id: {device_id!r}")
        dev.permissions[action_type] = level

    def permission_for(self, device_id: str, action_type: str) -> Optional[str]:
        """None si este dispositivo no tiene un permiso explícito para ese
        action_type — el llamador debe entonces caer a la política general de
        Security (nexus_core/security.py), no asumir PERMITIDO por defecto."""
        dev = self._devices.get(device_id)
        return dev.permissions.get(action_type) if dev else None

    def touch(self, device_id: str) -> None:
        dev = self._devices.get(device_id)
        if dev:
            dev.last_seen = time.time()
            dev.connected = True

    def disconnect(self, device_id: str) -> None:
        dev = self._devices.get(device_id)
        if dev:
            dev.connected = False
            if self._bus:
                self._bus.publish(ev.DEVICE_DISCONNECTED, device_id=device_id, name=dev.name)

    def revoke(self, device_id: str) -> bool:
        return self._devices.pop(device_id, None) is not None

    def list_devices(self) -> list[Device]:
        return list(self._devices.values())
