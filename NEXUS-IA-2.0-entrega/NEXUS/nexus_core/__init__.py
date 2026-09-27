"""
nexus_core — the modular core introduced to turn Mark-LIV into NEXUS IA 2.0.

Nothing in actions/, plugins/, memory/, core/, dashboard/ or ui.py was deleted
or rewritten to build this package. Every module here WRAPS existing,
working code (core.action_loader, core.plugin_loader, memory.memory_manager,
core.gemini, actions.screen_processor, actions.proactive,
actions.background_monitor, actions.dev_agent) rather than reimplementing it.
See main.py's module docstring for what changed there and why.

Submodules
----------
event_bus       EventBus       — internal pub/sub (USER_SPEECH, TOOL_STARTED, …)
security        Security       — per-tool risk level + confirmation gate
tool_manager    ToolManager    — one registry for inline + action + plugin tools
memory          NexusMemory    — short_term/episodic/semantic/procedural/
                                  projects/preferences view over memory_manager
brain           BrainRouter    — Fast/Deep/Vision routing (Gemini today; the
                                  seam future providers plug into)
perception      Perception     — screen/camera capture, wrapped with events
agent_manager   AgentManager   — proactive engine, monitors, dev_agent
planner         Planner        — NEW: multi-step task decomposition (MVP)
device_manager  DeviceManager  — NEW: in-memory registry of connected devices
voice           VoiceEngine    — the Gemini Live session loop (was JarvisLive
                                  in the old main.py; moved here verbatim,
                                  only the tool dispatch was rewired)
core            NexusCore      — wires all of the above together
"""
