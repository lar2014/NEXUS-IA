"""
nexus_core/event_bus.py — the internal event bus (NEXUS spec, section 6).

Why this exists
----------------
Today, main.py talks to the UI by calling `self.ui.xxx(...)` directly, and
every other module (memory, monitors, plugins) either returns a string or
pokes the UI the same way. That is fine for one process with one UI, but it
is exactly what has to change for a phone, a camera feed, or a future Nexus
Room to react to "the user just spoke" or "a tool finished" without every
producer knowing every consumer by name.

What this is
-------------
A small, synchronous, thread-safe pub/sub. Producers call `publish()`,
consumers call `subscribe()`. Handlers run synchronously on the publisher's
thread/task — so a handler must be fast (log a line, forward to a
WebSocket, update an in-memory registry). Anything slow must hand off to its
own thread/task; the bus does not do that for you, on purpose, so behaviour
stays predictable and this file stays small.

This does NOT replace `self.ui.write_log(...)` etc. today — VoiceEngine still
calls the UI directly, exactly as JarvisLive did, so nothing about how the
HUD updates changes. The bus is wired in ALONGSIDE those calls at the handful
of points that matter for a future multi-device Nexus (see voice.py's
`_emit(...)` calls). Migrating the rest of the UI callbacks onto the bus is a
later, separate step — not done here, to keep this change reviewable.

A short ring buffer of the most recent events is kept (mirrors the pattern
already used in dashboard/server.py's `_history[-50:]`), so a device that
connects late — or a future Nexus Room — can ask "what did I miss" instead of
only ever getting events from the moment it subscribed.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque

# ── Event type constants (exactly the set NEXUS asked for, plus a few the
#    existing app already needed a name for — see the comment on each). ─────
USER_SPEECH           = "USER_SPEECH"
VISION_UPDATE         = "VISION_UPDATE"
GESTURE_DETECTED      = "GESTURE_DETECTED"       # not produced yet — no gesture
                                                  # input exists in this codebase
                                                  # (see the audit); reserved for
                                                  # the mobile/Nexus Room agent.
TOOL_STARTED          = "TOOL_STARTED"
TOOL_FINISHED         = "TOOL_FINISHED"
AGENT_STARTED         = "AGENT_STARTED"
AGENT_FINISHED        = "AGENT_FINISHED"
MEMORY_UPDATED        = "MEMORY_UPDATED"
DEVICE_CONNECTED      = "DEVICE_CONNECTED"
CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"

# Extras — not asked for explicitly, but the existing app already has these
# moments and giving them names costs nothing and makes voice.py's intent
# readable at the call site.
DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED"
SESSION_CONNECTED    = "SESSION_CONNECTED"
SESSION_DISCONNECTED = "SESSION_DISCONNECTED"
ASSISTANT_SPEECH     = "ASSISTANT_SPEECH"

# ── Added for PROMPT 2 (NexusCore's text pipeline + Planner + Memory) ───────
# USER_MESSAGE / AI_RESPONSE are the channel-agnostic counterparts of
# USER_SPEECH / ASSISTANT_SPEECH above. voice.py keeps publishing the SPEECH
# pair (it already does, and every caller of it is tested) because a spoken
# turn is a more specific kind of message; USER_MESSAGE / AI_RESPONSE are for
# NexusCore.handle_text() (nexus_core/core.py) — any input that isn't a Live
# voice turn (dashboard, a future API, a Nexus Room typed command). Treat
# USER_MESSAGE as the general case and USER_SPEECH as one channel that
# publishes it, not as two unrelated events — a subscriber that only cares
# "did the user say something, in any form" should listen to both.
USER_MESSAGE   = "USER_MESSAGE"
AI_RESPONSE    = "AI_RESPONSE"

# Task-level events, one layer above TOOL_STARTED/FINISHED: a Planner Task
# (nexus_core/planner.py) is several tool calls, and nothing published an
# event for the task as a whole until now.
TASK_STARTED   = "TASK_STARTED"
TASK_COMPLETED = "TASK_COMPLETED"
TASK_FAILED    = "TASK_FAILED"

# MEMORY_UPDATED (above) already fires on every write and is what every
# existing subscriber should keep using for "something changed". These two
# are strictly more specific — published in addition to, not instead of,
# MEMORY_UPDATED — for a subscriber that cares which: MEMORY_CREATED only
# when the key did not exist before this write, MEMORY_RECALLED whenever
# NexusMemory.recall()/search() actually runs (a read, not a write).
MEMORY_CREATED  = "MEMORY_CREATED"
MEMORY_RECALLED = "MEMORY_RECALLED"

# Reserved, like GESTURE_DETECTED above: nothing in this codebase streams
# continuous camera frames today (actions/screen_processor.py captures one
# frame on demand — see the audit). Perception publishes VISION_UPDATE for
# that. CAMERA_FRAME is named now so a future continuous mobile/Nexus Room
# camera feed has a event to publish without another naming decision later.
CAMERA_FRAME = "CAMERA_FRAME"

_HISTORY_LEN = 200


@dataclass
class Event:
    type: str
    data: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


Handler = Callable[[Event], None]


class EventBus:
    """Process-local pub/sub. One instance lives on NexusCore and is handed
    to every module that needs to publish or subscribe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[Handler]] = {}
        self._wildcard: list[Handler] = []
        self._history: Deque[Event] = deque(maxlen=_HISTORY_LEN)

    def subscribe(self, event_type: str | None, handler: Handler) -> None:
        """`event_type=None` subscribes to every event (used by the dashboard
        relay and by logging/debug tooling)."""
        with self._lock:
            if event_type is None:
                self._wildcard.append(handler)
            else:
                self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str | None, handler: Handler) -> None:
        with self._lock:
            try:
                if event_type is None:
                    self._wildcard.remove(handler)
                else:
                    self._subscribers.get(event_type, []).remove(handler)
            except ValueError:
                pass

    def publish(self, event_type: str, **data: Any) -> Event:
        evt = Event(type=event_type, data=data)
        with self._lock:
            self._history.append(evt)
            handlers = list(self._subscribers.get(event_type, ())) + list(self._wildcard)
        for h in handlers:
            try:
                h(evt)
            except Exception as e:  # a bad subscriber must never break the publisher
                print(f"[EventBus] handler for {event_type} raised: {e}")
        return evt

    def history(self, event_type: str | None = None, limit: int = 50) -> list[Event]:
        with self._lock:
            items = list(self._history)
        if event_type:
            items = [e for e in items if e.type == event_type]
        return items[-limit:]
