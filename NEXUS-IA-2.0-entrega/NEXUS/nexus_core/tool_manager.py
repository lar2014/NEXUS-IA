"""
nexus_core/tool_manager.py — one registry for every tool (NEXUS spec, §3).

Mark-LIV already had two auto-discovering registries with an identical
contract — `core.action_loader.ActionRegistry` (built-in `actions/*.py`) and
`core.plugin_loader.PluginRegistry` (drop-in `plugins/*.py`). Both are kept
completely unchanged: rewriting a discovery/crash-isolation engine that
already works, just to make it "part of Nexus", would be exactly the
unnecessary rewrite the brief says not to do.

What's new here is the THIRD kind of tool Mark-LIV always had but never
named: the "inline" tools declared straight in main.py's TOOL_DECLARATIONS
(`save_memory`, `recall_memory`, `undo`, `screen_process`, `close_camera`,
`system_status`, `manage_monitor`, `shutdown_jarvis`). They stay inline —
their handlers reach into live session state (the pending-vision buffer, the
camera-stream flag, the shutdown sequence) that only VoiceEngine owns, and
faking that through a generic `run(name, params)` would either duplicate
that state here or bolt a callback system onto it for no real gain. Instead,
VoiceEngine registers their declarations with ToolManager (so they show up
in the single capability list the model and the UI see) and keeps executing
them itself — exactly the dispatch order `_execute_tool` already had:
inline names first, then actions, then plugins.

What ToolManager DOES centralise for all three kinds:
  * one merged list of tool declarations for the Live session config
    (previously assembled by hand in `_build_config`);
  * one `describe()` used to build the model's self-knowledge block
    (previously the free function `_describe_tools`);
  * risk level look-up via `nexus_core.security`;
  * TOOL_STARTED / TOOL_FINISHED events around every action/plugin run.
"""
from __future__ import annotations

import time
from typing import Optional

from core.action_loader import ActionRegistry
from core.plugin_loader import PluginRegistry
from nexus_core import event_bus as ev
from nexus_core.security import Security


class ToolManager:
    def __init__(self, action_registry: ActionRegistry, plugin_registry: PluginRegistry,
                 security: Security, bus: Optional["ev.EventBus"] = None) -> None:
        self._actions  = action_registry
        self._plugins  = plugin_registry
        self._security = security
        self._bus      = bus
        # name -> declaration dict, registered by VoiceEngine for the inline
        # tools it keeps executing itself (see module docstring).
        self._inline_decls: dict[str, dict] = {}

    # -- registration (called once by VoiceEngine at startup) ---------------
    def register_inline(self, declarations: list[dict]) -> None:
        for d in declarations:
            name = d.get("name") if isinstance(d, dict) else getattr(d, "name", None)
            if name:
                self._inline_decls[name] = d

    # -- discovery / declarations --------------------------------------------
    def get_all_declarations(self) -> list[dict]:
        """Everything the Live session's `tools=[...]` should carry — same
        set `_build_config` used to assemble by hand from three sources."""
        return (list(self._inline_decls.values())
                + self._actions.get_tool_declarations()
                + self._plugins.get_tool_declarations())

    def has(self, name: str) -> bool:
        return name in self._inline_decls or self._actions.has(name) or self._plugins.has(name)

    def is_inline(self, name: str) -> bool:
        return name in self._inline_decls

    def kind_of(self, name: str) -> str:
        if name in self._inline_decls:
            return "inline"
        if self._actions.has(name):
            return "action"
        if self._plugins.has(name):
            return "plugin"
        return "unknown"

    def names(self) -> set[str]:
        return set(self._inline_decls) | self._actions.names() | self._plugins.names()

    def scheduling(self, name: str) -> Optional[str]:
        """How a tool's result should re-enter the conversation, if it said
        (NON_BLOCKING tools only) — same lookup `_execute_tool` used to do
        against both registries by hand."""
        return self._actions.scheduling(name) or self._plugins.scheduling(name)

    def risk_of(self, name: str) -> str:
        decl = self._inline_decls.get(name)
        declared = decl.get("risk") if isinstance(decl, dict) else None
        return self._security.risk_of(name, declared)

    def describe(self) -> str:
        """One line per capability — same shape as the old `_describe_tools`
        free function in main.py, now fed by the merged declaration list."""
        lines = []
        for d in self.get_all_declarations() or ():
            name = d.get("name") if isinstance(d, dict) else getattr(d, "name", None)
            desc = (d.get("description") if isinstance(d, dict)
                    else getattr(d, "description", "")) or ""
            if not name:
                continue
            desc = " ".join(str(desc).split())
            lines.append(f"- {name}: {desc[:150]}" if desc else f"- {name}")
        return "\n".join(lines)

    # -- dispatch (actions + plugins only — see module docstring) -----------
    def run(self, name: str, parameters: dict, ctx: Optional[dict] = None) -> str:
        """Run an action or plugin tool. Inline tools are NOT dispatched
        here — VoiceEngine intercepts those names before calling this."""
        ctx = ctx or {}
        risk = self.risk_of(name)

        # PROMPT 2 §11: BLOCK is checked first and refuses outright — no
        # banner, nothing to confirm, the tool simply does not run. This is
        # the one policy outcome Phase 1 had no way to express at all.
        if self._security.is_blocked(name):
            return f"'{name}' is blocked by the current security policy and will not run."

        if self._security.requires_confirmation(name, risk):
            # ASK and not self-gated (see security.py's _SELF_GATED): park
            # it behind the confirmation banner instead of running it.
            return self._security.gate(
                tool_name=name,
                title=f"Run '{name}'",
                detail=f"Parameters: {parameters}",
                run=lambda: self._dispatch(name, parameters, ctx),
            )

        return self._dispatch(name, parameters, ctx)

    def _dispatch(self, name: str, parameters: dict, ctx: dict) -> str:
        if self._bus:
            self._bus.publish(ev.TOOL_STARTED, tool=name, kind=self.kind_of(name))
        t0 = time.monotonic()
        try:
            if self._actions.has(name):
                result = self._actions.run(name, parameters, ctx)
            elif self._plugins.has(name):
                result = self._plugins.run(
                    name, parameters,
                    player=ctx.get("player"),
                    session_memory=ctx.get("session_memory"),
                )
            else:
                result = f"Tool '{name}' is not available."
            return result
        finally:
            if self._bus:
                self._bus.publish(ev.TOOL_FINISHED, tool=name,
                                   elapsed_s=round(time.monotonic() - t0, 3))

    # -- UI surfaces (unchanged passthroughs, kept here so ui.py has one
    #    place to ask instead of reaching into two registries) --------------
    def list_plugins_for_ui(self) -> list[dict]:
        return self._plugins.list_for_ui()

    def plugin_settings_schemas(self) -> list[dict]:
        return self._plugins.settings_schemas()
