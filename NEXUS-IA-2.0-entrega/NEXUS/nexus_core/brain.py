"""
nexus_core/brain.py — BrainRouter (NEXUS spec, §2).

"Si Mark-LIV utiliza Gemini Live actualmente, conserva su integración como
proveedor compatible" — this file does not touch `core/gemini.py` (the
Fast/Smart/Search ladder with timeouts and fallback, used today by
code_helper, dev_agent, file_processor, web_search, flight_finder, desktop,
youtube_video and computer_control) or the Live session in
`nexus_core/voice.py`. It wraps the former behind names that match the brief
("Fast Brain / Deep Brain / Vision Brain") and gives future providers
(OpenAI, Anthropic, a local model via the currently-dead
`core/llm_client.py` — see the audit) exactly one seam to plug into.

Today there is exactly one provider (Gemini), so `BrainRouter` is a thin
pass-through — this is intentional, not a placeholder waiting to be filled:
the brief is explicit that Nexus must work with only one provider configured,
so "one provider wired in" is the correct, complete state for this step, not
an unfinished one.

Nothing that already calls `from core import gemini` directly was changed —
eight files do that today, and rewriting all eight to go through BrainRouter
instead is exactly the kind of unnecessary, high-risk rewrite the brief asks
to avoid for something that isn't broken. New code (Planner, AgentManager)
uses BrainRouter; existing actions keep working exactly as they do today.
"""
from __future__ import annotations

# ── Intent categories (PROMPT 2, §5) ────────────────────────────────────────
# What's genuinely new here: BrainRouter above already routes by MODEL TIER
# (fast/deep/vision/search) — that was Phase 1. This is a different axis,
# routing by what the user is asking for, so NexusCore.handle_text()
# (nexus_core/core.py) knows whether to hand the request straight to a tool,
# to Planner first, or to nothing (a plain chat reply). It's an addition to
# THIS class, not a second BrainRouter.
#
# One thing worth being honest about: the Live voice session in voice.py
# does NOT use this. Gemini's own function-calling already decides, turn by
# turn, which of the ~17 tools to invoke while talking — that IS routing,
# and it already works, tested, in Phase 1. Running a hand-rolled classifier
# in front of it would second-guess a model that already has the full
# conversation and the tool declarations, for no benefit. `classify()` exists
# for the channel that does NOT have that: text arriving outside the Live
# session (dashboard, a future API), which is exactly why it is called from
# `NexusCore.handle_text()` and nowhere in voice.py.
INTENTS = (
    "CHAT", "QUESTION", "RESEARCH", "COMPUTER_ACTION", "FILE_ACTION", "CODE",
    "PLANNING", "AUTOMATION", "VISION", "MEMORY", "SYSTEM_ACTION", "OTHER",
)

_CLASSIFY_PROMPT = """Classify the user's request into EXACTLY ONE of these \
categories: {intents}

CHAT — small talk, greetings, opinions, nothing to look up or do.
QUESTION — a factual question answerable from general knowledge.
RESEARCH — needs looking something up (web search, current info).
COMPUTER_ACTION — control the computer (open an app, change a setting).
FILE_ACTION — read, write, move, or organise files/documents.
CODE — write, explain, or debug code.
PLANNING — a multi-step task that should be broken down first.
AUTOMATION — set up something recurring (a monitor, a reminder, a routine).
VISION — needs to look at the screen or camera.
MEMORY — save or recall something about the user.
SYSTEM_ACTION — check or change the assistant/system's own state.
OTHER — none of the above fit.

Request: {text}

Respond with ONLY the category name, nothing else."""




class BrainRouter:
    """Fast / Deep / Vision, routed to whatever provider(s) are configured.
    Today: always core.gemini. The three methods are the extension seam —
    a future provider is added by branching inside them, not by changing
    any caller."""

    def __init__(self) -> None:
        self.provider_name = "gemini"

    def fast(self, prompt: str, *, timeout_ms: int = 15_000, default: str = "") -> str:
        """Short classification / extraction / one-line decisions. Returns
        plain text (via core.gemini.text — the existing reduced-to-a-string
        helper), `default` if every rung of the ladder failed."""
        from core import gemini
        return gemini.text(prompt, tier=gemini.FAST, timeout_ms=timeout_ms, default=default)

    def deep(self, prompt: str, *, timeout_ms: int = 45_000, default: str = "") -> str:
        """Reasoning, generation, long documents — used by Planner and
        AgentManager for multi-step decomposition."""
        from core import gemini
        return gemini.text(prompt, tier=gemini.SMART, timeout_ms=timeout_ms, default=default)

    def deep_json(self, prompt: str, *, timeout_ms: int = 45_000, default=None):
        """Same as `deep`, parsed as JSON — for Planner's step lists. Uses
        core.gemini.as_json, which already tolerates markdown-fenced output."""
        from core import gemini
        return gemini.as_json(prompt, tier=gemini.SMART, timeout_ms=timeout_ms, default=default)

    def vision(self, image_bytes: bytes, mime_type: str, prompt: str,
               *, timeout_ms: int = 45_000, default: str = "") -> str:
        """Analyse one image (screen or camera frame) with a text prompt.
        Mirrors exactly what actions/code_helper.py already does by hand —
        centralised here so Perception and future tools don't repeat it."""
        from google.genai import types
        from core import gemini
        contents = [types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt]
        return gemini.text(contents, tier=gemini.SMART, timeout_ms=timeout_ms, default=default)

    def search(self, query: str, *, timeout_ms: int = 20_000, default: str = "") -> str:
        """Grounded web search — REST only, per core/gemini.py's own notes
        (the Live throwaway-session path can't carry grounding metadata)."""
        from core import gemini
        return gemini.text(query, tier=gemini.SEARCH, timeout_ms=timeout_ms, default=default)

    def classify(self, text: str) -> str:
        """One of the INTENTS above. Falls back to "OTHER" — never raises,
        never returns something NexusCore.handle_text() doesn't recognise —
        whenever the model call fails (no API key, offline, malformed
        reply) or answers with something off the list."""
        reply = self.fast(_CLASSIFY_PROMPT.format(intents=", ".join(INTENTS), text=text),
                           timeout_ms=8_000, default="")
        candidate = reply.strip().upper().split()[0] if reply.strip() else ""
        candidate = candidate.strip(' ."\'.,')
        return candidate if candidate in INTENTS else "OTHER"
