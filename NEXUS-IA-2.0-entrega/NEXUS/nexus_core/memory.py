"""
nexus_core/memory.py — NexusMemory (NEXUS spec, §5).

"No rompas la memoria existente. [...] La implementación puede utilizar
inicialmente el sistema existente de Mark-LIV." — this file does exactly
that: `memory/memory_manager.py` and `memory/long_term.json` are UNCHANGED
in format (one additive empty category, "procedural" — see the diff in
memory_manager.py's `_empty_memory()` — every existing file loads exactly as
before). NexusMemory is a view over the six real categories, not a new
store:

    short_term   -> in-RAM only, this VoiceEngine session's turns. Never
                    written to disk directly; feeds `episodic` at the end of
                    a session via the existing save_session_summary().
    episodic     -> memory["sessions"]           (already existed)
    semantic     -> memory["identity"] + memory["notes"]   (already existed,
                    combined: identity is "who they are", notes is "what's
                    true about their world" — both are facts, not tasks)
    procedural   -> memory["procedural"]          (new, empty, reserved)
    projects     -> memory["projects"]            (already existed)
    preferences  -> memory["preferences"]         (already existed)

`relationships` and `wishes` still exist in the underlying store and are
still fully readable/writable through `memory_manager` directly (e.g. by
recall_memory, which searches the whole store) — NexusMemory just doesn't
put them behind one of the six named views above, because the brief didn't
ask for a view named that and inventing one it didn't ask for would be
exactly the kind of unrequested restructuring to avoid.
"""
from __future__ import annotations

from typing import Optional

from memory import memory_manager as mm
from nexus_core import event_bus as ev

_IDENTITY_KEYS = set(mm._IDENTITY_FIELDS)


class NexusMemory:
    def __init__(self, bus: Optional["ev.EventBus"] = None) -> None:
        self._bus = bus
        self.short_term: list[str] = []   # this session's turns; not persisted here

    # -- raw passthroughs — for callers that legitimately need the whole
    #    store or an arbitrary category (e.g. the `save_memory` tool, which
    #    lets the MODEL pick any of the 7 categories by name; narrowing that
    #    to the 6 named views below would change its behaviour) -------------
    def raw_all(self) -> dict:
        return mm.load_memory()

    def update(self, category: str, key: str, value: str) -> None:
        """Write to an arbitrary category, exactly as memory_manager always
        allowed. Used by the `save_memory` tool (voice.py), which lets the
        model choose the category itself. `remember()` below is this same
        method under the name PROMPT 2 asked for."""
        existed = key in mm.load_memory().get(category, {})
        mm.update_memory({category: {key: {"value": value}}})
        self._touched(category, key, created=not existed)

    def remember(self, category: str, key: str, value: str) -> None:
        """PROMPT 2 §6's `remember()`. Not a second write path — calls
        `update()` above, which is the one write path this class has."""
        self.update(category, key, value)

    def identity_get_all(self) -> dict:
        return dict(mm.load_memory().get("identity", {}))

    def set_trim_notifier(self, fn) -> None:
        mm.set_trim_notifier(fn)

    # -- semantic (identity + notes) -----------------------------------------
    def semantic_set(self, key: str, value: str) -> None:
        category = "identity" if key in _IDENTITY_KEYS else "notes"
        mm.update_memory({category: {key: {"value": value}}})
        self._touched(category, key)

    def semantic_get_all(self) -> dict:
        memory = mm.load_memory()
        out = dict(memory.get("identity", {}))
        out.update(memory.get("notes", {}))
        return out

    # -- procedural -----------------------------------------------------------
    def procedural_set(self, key: str, value: str) -> None:
        mm.update_memory({"procedural": {key: {"value": value}}})
        self._touched("procedural", key)

    def procedural_get_all(self) -> dict:
        return dict(mm.load_memory().get("procedural", {}))

    # -- projects / preferences — direct passthroughs ------------------------
    def projects_set(self, key: str, value: str) -> None:
        mm.update_memory({"projects": {key: {"value": value}}})
        self._touched("projects", key)

    def projects_get_all(self) -> dict:
        return dict(mm.load_memory().get("projects", {}))

    def preferences_set(self, key: str, value: str) -> None:
        mm.update_memory({"preferences": {key: {"value": value}}})
        self._touched("preferences", key)

    def preferences_get_all(self) -> dict:
        return dict(mm.load_memory().get("preferences", {}))

    # -- episodic --------------------------------------------------------------
    def episodic_add(self, summary: str, language: str = "") -> None:
        mm.save_session_summary(summary, language)
        self._touched("episodic", "session")

    def episodic_pop_last(self) -> dict | None:
        return mm.pop_last_session()

    # -- short_term --------------------------------------------------------------
    def short_term_add(self, line: str) -> None:
        self.short_term.append(line)

    def short_term_clear(self) -> None:
        self.short_term = []

    # -- cross-cutting: unchanged from memory_manager, exposed here so
    #    callers only need one import -----------------------------------------
    def recall(self, query: str, limit: int = 8) -> str:
        result = mm.search_memory(query, limit=limit)
        if self._bus:
            self._bus.publish(ev.MEMORY_RECALLED, query=query)
        return result

    def search(self, query: str, limit: int = 8) -> str:
        """PROMPT 2 §6's `search()`. Today `memory_manager` has exactly one
        lookup mechanism — a lexical scan over stored facts (see
        `mm.search_memory`) — so `search()` and `recall()` are the same
        operation under two names. If Nexus later grows a real distinction
        (recall = fetch one known fact by key, search = fuzzy lookup across
        everything), this is where they'd diverge — not invented today on
        the strength of a name alone."""
        return self.recall(query, limit=limit)

    def format_for_prompt(self) -> str:
        return mm.format_memory_for_prompt(mm.load_memory())

    def all_entries_for_ui(self) -> list[dict]:
        return mm.all_entries_for_ui()

    def forget(self, key: str, category: str = "notes") -> str:
        result = mm.forget(key, category)
        self._touched(category, key)
        return result

    # -- internal ---------------------------------------------------------------
    def _touched(self, category: str, key: str, created: bool = False) -> None:
        if not self._bus:
            return
        if created:
            self._bus.publish(ev.MEMORY_CREATED, category=category, key=key)
        self._bus.publish(ev.MEMORY_UPDATED, category=category, key=key)
