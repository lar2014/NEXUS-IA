"""
nexus_core/planner.py — Planner (NEXUS spec, §1 core layout).

Genuinely NEW code, not a wrapper — Mark-LIV had no explicit planning step
before this (the closest thing, `dev_agent._plan_project`, plans one kind of
task — a software project — internally to itself, and stays exactly as it
is; see agent_manager.py's docstring). Called by nothing yet, so it changes
the behaviour of nothing that already works: it's an opt-in capability
future tool-calling logic (e.g. a "do this multi-step thing" inline tool, or
AgentManager) can call into.

Deliberately small: it asks BrainRouter.deep_json for an ordered list of
steps, each naming which tool (by name, as ToolManager already knows it)
would do that step, and returns that list. It does NOT execute anything —
executing a plan safely (respecting Security's risk gate per step, handling
a step that fails) is a separate concern for whatever drives the plan, kept
out of this file on purpose so Planner stays test-able in isolation.

PROMPT 2 §7 addition: `plan()` above returns a flat list — useful, but not
something a caller can track progress on or report a failure against. `Task`
/ `Step` give the same plan a trackable shape (matches §7's diagram: Task →
Step 1..N → Final result) and the four bookkeeping methods below cover §15's
Planner tests (create a task, multiple steps, complete it, handle an error).
This is still not an execution engine — `mark_step_done/failed` are called
BY whatever drives the task (NexusCore.handle_text, nexus_core/core.py) as
each step actually runs; Planner just remembers what happened.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from nexus_core.brain import BrainRouter
from nexus_core.tool_manager import ToolManager

_PROMPT = """You are the planning module of a personal assistant. Break the \
following request into an ordered list of short steps. For each step, name \
the single tool (from the list below) that would carry it out, or "none" if \
it needs no tool (e.g. just a spoken answer).

Available tools:
{tools}

Request: {request}

Respond with ONLY a JSON array, no prose, no markdown fences. Each item:
{{"step": "<short description>", "tool": "<tool name or none>"}}
"""


class StepStatus(str, Enum):
    PENDING = "PENDING"
    DONE    = "DONE"
    FAILED  = "FAILED"


class TaskStatus(str, Enum):
    PENDING   = "PENDING"
    RUNNING   = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"


@dataclass
class Step:
    description: str
    tool: str
    status: StepStatus = StepStatus.PENDING
    result: str | None = None
    error: str | None = None


@dataclass
class Task:
    id: str
    request: str
    steps: list[Step] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    final_result: str | None = None


class Planner:
    def __init__(self, brain: BrainRouter, tool_manager: ToolManager) -> None:
        self._brain = brain
        self._tools = tool_manager

    def plan(self, request: str) -> list[dict]:
        """Return an ordered list of {"step": ..., "tool": ...} dicts, or []
        if the request doesn't decompose (or the model call failed — see
        BrainRouter.deep_json's `default`)."""
        tool_names = ", ".join(sorted(self._tools.names())) or "(none discovered)"
        prompt = _PROMPT.format(tools=tool_names, request=request)
        steps = self._brain.deep_json(prompt, default=[])
        if not isinstance(steps, list):
            return []
        out = []
        for s in steps:
            if not isinstance(s, dict) or not s.get("step"):
                continue
            tool = str(s.get("tool") or "none").strip()
            if tool != "none" and not self._tools.has(tool):
                tool = "none"   # the model named a tool that doesn't exist — don't pretend
            out.append({"step": str(s["step"]).strip(), "tool": tool})
        return out

    # -- Task/Step bookkeeping (PROMPT 2 §7) ---------------------------------
    def create_task(self, request: str) -> Task:
        """Plan the request and wrap the result as a trackable Task. Every
        step starts PENDING; nothing has run yet."""
        steps = [Step(description=s["step"], tool=s["tool"]) for s in self.plan(request)]
        return Task(id=uuid.uuid4().hex[:12], request=request, steps=steps)

    def mark_step_done(self, task: Task, index: int, result: str) -> None:
        task.steps[index].status = StepStatus.DONE
        task.steps[index].result = result
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.RUNNING

    def mark_step_failed(self, task: Task, index: int, error: str) -> None:
        """A failed step fails the task — Planner does not decide whether to
        retry or skip; that policy belongs to whatever is driving the task."""
        task.steps[index].status = StepStatus.FAILED
        task.steps[index].error = error
        task.status = TaskStatus.FAILED

    def complete_task(self, task: Task, final_result: str) -> Task:
        """Mark the task COMPLETED with its final result — a no-op if it
        already FAILED, so a late completion can't paper over an error."""
        if task.status != TaskStatus.FAILED:
            task.status = TaskStatus.COMPLETED
            task.final_result = final_result
        return task

    def is_done(self, task: Task) -> bool:
        return all(s.status == StepStatus.DONE for s in task.steps)
