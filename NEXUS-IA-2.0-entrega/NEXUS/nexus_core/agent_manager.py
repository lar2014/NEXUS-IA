"""
nexus_core/agent_manager.py — AgentManager (NEXUS spec, §1 core layout).

Mark-LIV already had three things that behave like "agents" (they act
without a fresh explicit instruction each time), scattered across
actions/*.py and driven by hand from main.py's session loop. None of their
own logic is rewritten here — this module gives them one place to be listed
and one place to emit AGENT_STARTED / AGENT_FINISHED, nothing more:

  * `actions/dev_agent.py` — genuinely multi-step: plans a project
    (`_plan_project`), writes files, installs dependencies, runs the result,
    reads the traceback back and retries. This is the closest thing in the
    whole codebase to what NEXUS objective 7 ("ejecutar tareas de varios
    pasos") asks for. It is already registered as an ordinary TOOL in
    `core.action_loader`, so AgentManager runs it THROUGH ToolManager
    (inheriting its risk gating — dev_agent is classified HIGH in
    security.py) rather than importing and calling it a second, parallel
    way.

  * `actions/proactive.py`'s `ProactiveEngine` — a small state machine
    (`should_trigger` / `mark_triggered` / `build_prompt`) that decides when
    the assistant should speak unprompted. VoiceEngine still owns and drives
    the instance directly, exactly as JarvisLive did — moving the driving
    loop here would mean AgentManager reaching back into live session state
    (whether JARVIS is currently speaking, the last user-speech timestamp),
    which is exactly the coupling the module docstring in tool_manager.py
    explains why inline tools stay inline. AgentManager only holds a
    reference so `list_agents()` can report it exists.

  * `actions/background_monitor.py` — topic watching, checked once a day.
    Its four functions (`add_monitor` / `remove_monitor` / `list_monitors` /
    `check_all`) are the same ones the inline `manage_monitor` tool and
    VoiceEngine's `_run_background_monitor` loop already call; AgentManager
    wraps `check_all` with AGENT_STARTED/FINISHED so a monitor sweep is
    visible on the event bus the same way a dev_agent run is.

PROMPT 2 §8 asks for named, non-overlapping "specialized agents"
(PersonalAgent, ResearchAgent, ComputerAgent, ...). `_SPECIALIZED_AGENTS`
below is that — but it is a PERMISSION GROUPING over the 24 tools Phase 1
already discovered (16 actions + 8 inline), not new agent logic: every tool
still runs exactly the same way, through `ToolManager.run()`.  Each tool
belongs to exactly one agent ("no hagas que todos puedan hacer todo") —
`run_as()` below refuses a tool that isn't in the calling agent's set.
Three tools are deliberately unassigned: `screen_process` / `close_camera`
(live-session state VoiceEngine owns directly, same reason they're inline
and not in ToolManager's dispatch — see tool_manager.py) and
`shutdown_jarvis` (exits the assistant itself, not a task any agent should
be doing on the user's behalf). Nothing calls `run_as()` yet — same
"interface ready, no caller forcing its shape yet" status as Planner had
after Phase 1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from actions import background_monitor as _bg
from actions.proactive import ProactiveEngine
from nexus_core import event_bus as ev
from nexus_core.tool_manager import ToolManager


@dataclass(frozen=True)
class Agent:
    name: str
    description: str
    tools: frozenset[str]


_SPECIALIZED_AGENTS: dict[str, Agent] = {
    "PersonalAgent": Agent(
        "PersonalAgent", "Memory, reminders, monitors, messages — the user's own context.",
        frozenset({"save_memory", "recall_memory", "reminder", "manage_monitor",
                   "undo", "send_message"})),
    "ResearchAgent": Agent(
        "ResearchAgent", "Looks things up: web, weather, flights, video.",
        frozenset({"web_search", "weather_report", "flight_finder", "youtube_video"})),
    "ComputerAgent": Agent(
        "ComputerAgent", "Controls the machine itself: apps, settings, desktop, status.",
        frozenset({"computer_control", "computer_settings", "desktop_control",
                   "open_app", "system_status", "game_updater"})),
    "CodingAgent": Agent(
        "CodingAgent", "Writes, runs, and debugs code.",
        frozenset({"dev_agent", "code_helper"})),
    "BrowserAgent": Agent(
        "BrowserAgent", "Automates the web browser on the user's behalf.",
        frozenset({"browser_control"})),
    "FileAgent": Agent(
        "FileAgent", "Reads, writes, converts, and organises files/documents.",
        frozenset({"file_controller", "file_processor"})),
    "PlanningAgent": Agent(
        "PlanningAgent", "Owns no tools of its own — decomposes a request via Planner, "
                          "then hands each step to whichever agent owns that step's tool.",
        frozenset()),
}


class AgentManager:
    def __init__(self, tool_manager: ToolManager, bus: Optional["ev.EventBus"] = None,
                 proactive_engine: Optional[ProactiveEngine] = None) -> None:
        self._tools = tool_manager
        self._bus = bus
        # VoiceEngine passes its own instance in (it needs to drive it against
        # live session state); AgentManager creates one only if none is given,
        # so `list_agents()` still has something to report before a session
        # exists.
        self.proactive = proactive_engine or ProactiveEngine()

    def list_agents(self) -> list[dict]:
        return [
            {"name": "dev_agent", "kind": "tool-backed", "risk": self._tools.risk_of("dev_agent")},
            {"name": "proactive", "kind": "session-driven", "risk": "LOW"},
            {"name": "background_monitor", "kind": "scheduled", "risk": "LOW"},
        ]

    # -- specialized agents (PROMPT 2 §8) ------------------------------------
    def list_specialized_agents(self) -> list[dict]:
        return [{"name": a.name, "description": a.description, "tools": sorted(a.tools)}
                for a in _SPECIALIZED_AGENTS.values()]

    def tools_for_agent(self, agent_name: str) -> frozenset[str]:
        agent = _SPECIALIZED_AGENTS.get(agent_name)
        if agent is None:
            raise ValueError(f"unknown agent: {agent_name!r}")
        return agent.tools

    def agent_for_tool(self, tool_name: str) -> Optional[str]:
        for agent in _SPECIALIZED_AGENTS.values():
            if tool_name in agent.tools:
                return agent.name
        return None   # one of the 3 deliberately unassigned tools, or unknown

    def run_as(self, agent_name: str, tool_name: str, parameters: dict,
               ctx: Optional[dict] = None) -> str:
        """Run `tool_name` AS `agent_name` — refuses if that tool isn't one
        of this agent's own tools (the "no todos pueden hacer todo" rule),
        then dispatches through ToolManager exactly like run_dev_agent()
        does below, so Security's risk gating still applies unchanged."""
        if tool_name not in self.tools_for_agent(agent_name):
            return (f"{agent_name} does not have '{tool_name}' — it can use: "
                     f"{', '.join(sorted(self.tools_for_agent(agent_name))) or '(nothing)'}")
        self._emit_start(agent_name)
        try:
            return self._tools.run(tool_name, parameters, ctx or {})
        finally:
            self._emit_finish(agent_name)

    def run_dev_agent(self, parameters: dict, ctx: Optional[dict] = None) -> str:
        self._emit_start("dev_agent")
        try:
            return self._tools.run("dev_agent", parameters, ctx or {})
        finally:
            self._emit_finish("dev_agent")

    # -- background monitors --------------------------------------------------
    def add_monitor(self, topic: str) -> str:
        return _bg.add_monitor(topic)

    def remove_monitor(self, topic: str) -> str:
        return _bg.remove_monitor(topic)

    def list_monitors(self) -> list[str]:
        return _bg.list_monitors()

    def check_monitors(self) -> list[str]:
        self._emit_start("background_monitor")
        try:
            return _bg.check_all()
        finally:
            self._emit_finish("background_monitor")

    # -- internal ---------------------------------------------------------------
    def _emit_start(self, name: str) -> None:
        if self._bus:
            self._bus.publish(ev.AGENT_STARTED, agent=name)

    def _emit_finish(self, name: str) -> None:
        if self._bus:
            self._bus.publish(ev.AGENT_FINISHED, agent=name)
