"""
nexus_core/perception.py — screen & camera capture, with events.

Wraps `actions.screen_processor._capture_screen` / `_capture_camera` — the
exact functions VoiceEngine's `screen_process` tool already calls — and adds
a VISION_UPDATE publish so any subscriber (a future mobile client mirroring
what the assistant is looking at, a Nexus Room display) can react without
VoiceEngine having to know they exist.

Not changed: `actions/screen_processor.py` itself. Per the audit, it already
does the right thing for images (compress in RAM, hand back bytes, persist
nothing) — nothing here writes a frame to disk either. If/when Nexus adds
`NEXUS_DATA/images/`, that's a decision for whoever calls Perception (e.g. "the
user asked to keep this one"), not something Perception does on its own.
"""
from __future__ import annotations

from typing import Optional

from actions.screen_processor import _capture_camera, _capture_screen
from nexus_core import event_bus as ev


class Perception:
    def __init__(self, bus: Optional["ev.EventBus"] = None) -> None:
        self._bus = bus

    def capture_screen(self) -> tuple[bytes, str]:
        img_bytes, mime = _capture_screen()
        self._emit("screen", len(img_bytes))
        return img_bytes, mime

    def capture_camera(self) -> tuple[bytes, str]:
        img_bytes, mime = _capture_camera()
        self._emit("camera", len(img_bytes))
        return img_bytes, mime

    def _emit(self, source: str, size_bytes: int) -> None:
        if self._bus:
            self._bus.publish(ev.VISION_UPDATE, source=source, bytes=size_bytes)
