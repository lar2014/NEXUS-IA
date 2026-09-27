"""
nexus_core/core.py — NexusCore, the top-level orchestrator (NEXUS spec §1).

This is where the one-time discovery step that used to open JarvisLive.__init__
now happens: `core.action_loader.discover_actions()` and
`core.plugin_loader.discover_plugins()` are called exactly as before, with the
exact same arguments (actions_dir, plugins_dir, reserved/core names, loggers).
Nothing about HOW actions/plugins are found, validated, or crash-isolated
changed — only WHO calls it moved, from VoiceEngine's constructor to here, so
VoiceEngine no longer needs to know the discovery mechanics at all — it just
receives a ready ToolManager.

NexusCore.run() is what main.py now calls. It is a thin pass-through to
VoiceEngine.run() today (there is exactly one "session" — the Gemini Live
voice session — for NexusCore to run), but it is the seam a future non-voice
entry point (a text-only dashboard driver, a Nexus Room daemon) would call
into instead of importing VoiceEngine directly.

PROMPT 2 §4 addition: `handle_text()` below is the explicit
Input → Context → Brain → Planner (if needed) → Tool → Result →
Memory/EventBus → Response pipeline the brief asks for. It is a SEPARATE
path from `run()`/VoiceEngine, not a replacement for how the Live session
already dispatches tools — worth being explicit about why, since it would
be easy to assume otherwise: inside a Live voice turn, Gemini's own
function-calling already IS that pipeline (it reads the conversation, picks
a tool from the declarations, and VoiceEngine dispatches it — tested, in
Phase 1). Running BrainRouter.classify() in front of that would be a second,
weaker router second-guessing a model that already has more context than a
classifier prompt does. `handle_text()` exists for the channel that has NO
Gemini turn doing that already — text arriving outside the Live session
(the dashboard's `/ws` text commands today; a future non-voice API
tomorrow). It is genuinely new, unused by voice.py, and safe to add: nothing
already-working calls it, so nothing already-working can break from it.
"""
from __future__ import annotations

from pathlib import Path

from core.action_loader import discover_actions
from core.plugin_loader import discover_plugins
from ui import JarvisUI

from nexus_core import event_bus as evbus
from nexus_core.agent_manager import AgentManager
from nexus_core.brain import BrainRouter
from nexus_core.device_manager import DeviceManager
from nexus_core.memory import NexusMemory
from nexus_core.perception import Perception
from nexus_core.planner import Planner
from nexus_core.security import Security
from nexus_core.tool_manager import ToolManager
from nexus_core.voice import TOOL_DECLARATIONS, VoiceEngine

# Intents handled by asking Planner to break the request into steps (each
# step names a tool, dispatched through ToolManager exactly as any other
# tool call is). VISION is included for completeness (PROMPT 2's category
# list) but is a known gap, not a working path — see handle_text()'s
# docstring and the migration report's "qué queda pendiente".
_TOOL_INTENTS = {
    "RESEARCH", "COMPUTER_ACTION", "FILE_ACTION", "CODE",
    "PLANNING", "AUTOMATION", "VISION", "SYSTEM_ACTION",
}


class NexusCore:
    def __init__(self, ui: JarvisUI, base_dir: Path | None = None) -> None:
        base_dir = base_dir or Path(__file__).resolve().parent.parent

        self.bus = evbus.EventBus()

        # -- discovery: identical call, identical arguments to the old
        #    JarvisLive.__init__ (see core/action_loader.py, core/plugin_loader.py) --
        _inline_names = {t["name"] for t in TOOL_DECLARATIONS}
        action_registry = discover_actions(
            actions_dir=base_dir / "actions",
            reserved_names=_inline_names,
            logger=lambda msg: print(f"[Actions] {msg}"),
        )
        _core_names = _inline_names | action_registry.names()
        plugin_registry = discover_plugins(
            plugins_dir=base_dir / "plugins",
            core_tool_names=_core_names,
            logger=lambda msg: print(f"[Plugins] {msg}"),
            notify=lambda msg: ui.write_log(f"SYS: {msg}"),
        )

        self.security  = Security(bus=self.bus)
        self.tools     = ToolManager(action_registry, plugin_registry, self.security, bus=self.bus)
        self.memory    = NexusMemory(bus=self.bus)
        self.brain     = BrainRouter()
        self.perception = Perception(bus=self.bus)
        self.agent_manager = AgentManager(self.tools, bus=self.bus)
        self.planner   = Planner(self.brain, self.tools)
        self.devices   = DeviceManager(bus=self.bus)

        self.voice = VoiceEngine(
            ui, self.tools, self.memory, self.bus, self.security,
            self.brain, self.perception, self.agent_manager,
        )

    async def run(self) -> None:
        await self.voice.run()

    # -- PROMPT 2 §4: the explicit text pipeline — see this module's
    #    docstring for why this is separate from run()/VoiceEngine. --------
    def handle_text(self, user_input: str, device_id: str | None = None) -> str:
        """Input → Context → Brain → Planner (if needed) → Tool → Result →
        Memory/EventBus → Response, synchronous and side-effect-free on
        anything voice.py owns (no session, no audio, no UI state)."""
        self.bus.publish(evbus.USER_MESSAGE, text=user_input, device_id=device_id)

        intent = self.brain.classify(user_input)

        if intent == "MEMORY":
            response = self.memory.search(user_input) or "I found nothing matching that."
        elif intent in _TOOL_INTENTS:
            response = self._run_task(user_input)
        else:   # CHAT, QUESTION, OTHER — and anything classify() didn't recognise
            response = self.brain.deep(user_input, default="I don't have an answer for that right now.")

        self.bus.publish(evbus.AI_RESPONSE, text=response, intent=intent)
        return response

    def _run_task(self, user_input: str) -> str:
        """Plan the request, run each step's tool through ToolManager,
        record progress on the Task via Planner's own bookkeeping, and
        publish TASK_STARTED/COMPLETED/FAILED around the whole thing."""
        task = self.planner.create_task(user_input)
        self.bus.publish(evbus.TASK_STARTED, task_id=task.id, request=user_input,
                          steps=len(task.steps))

        if not task.steps:
            self.bus.publish(evbus.TASK_FAILED, task_id=task.id, reason="no steps produced")
            return "I couldn't break that down into anything actionable."

        results = []
        for i, step in enumerate(task.steps):
            try:
                result = step.description if step.tool == "none" else self.tools.run(step.tool, {}, {})
                self.planner.mark_step_done(task, i, result)
                results.append(result)
            except Exception as e:
                self.planner.mark_step_failed(task, i, str(e))
                self.bus.publish(evbus.TASK_FAILED, task_id=task.id, step=i, reason=str(e))
                return f"Step {i + 1} ('{step.description}') failed: {e}"

        final = "\n".join(str(r) for r in results if r)
        self.planner.complete_task(task, final)
        self.bus.publish(evbus.TASK_COMPLETED, task_id=task.id)
        return final
