"""
Optional secondary sink for STRUCTURED events about this run's progress --
which subagent is currently running, the orchestrator's live todo list,
which skills have been read, how many auto-continue attempts have fired.

This is deliberately a separate, parallel mechanism from `agent/logsink.py`
rather than an extension of it: `logsink` carries free-text terminal lines
(unconditionally, always printed) for a human tailing a log; this carries
typed `dict` events for a caller that wants to render live structured UI
(a todo checklist, a "currently running: X" banner, per-skill/subagent
usage counts -- see `frontend/app.py`'s `RunStateAggregator` usage) without
having to parse text. Nothing here ever touches stdout -- if no sink is
registered, an emitted event is simply dropped, same tradeoff `logsink`
makes in reverse.

Process-wide, not per-thread or per-run -- same constraint as `logsink.py`
and for the same reason: this only works correctly because the pipeline
currently supports at most one generation running at a time in a given
process (see `frontend/app.py`'s single-job-at-a-time design). If that ever
changes, this needs to become `contextvars`-based instead.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_sink: Callable[[dict[str, Any]], None] | None = None


def set_sink(sink: Callable[[dict[str, Any]], None] | None) -> None:
    global _sink
    _sink = sink


def emit(event: dict[str, Any]) -> None:
    """Pass-through only, no aggregation here -- see `RunStateAggregator`
    below for the stateful view a UI actually wants."""
    if _sink is not None:
        _sink(event)


class RunStateAggregator:
    """Folds a stream of `emit()`-shaped events into one live snapshot.

    Not thread-safe on its own -- the same single-sink caveat as the module
    docstring applies; `frontend/app.py` protects both the sink registration
    and every `.handle()` call with the same lock it already uses for
    `logsink`.
    """

    def __init__(self) -> None:
        self._run_dir: str | None = None
        self._todos: list[dict[str, str]] = []
        self._current_phase: dict[str, str] | None = None
        # {subagent_name: {"calls": int, "total_seconds": float, "errors": int}}
        self._subagent_usage: dict[str, dict[str, float]] = {}
        # {skill_name: {"reads": int}}
        self._skill_usage: dict[str, dict[str, int]] = {}
        self._auto_continue_attempts = 0

    def _subagent_bucket(self, name: str) -> dict[str, float]:
        return self._subagent_usage.setdefault(name, {"calls": 0, "total_seconds": 0.0, "errors": 0})

    def handle(self, event: dict[str, Any]) -> None:
        etype = event.get("type")

        if etype == "run_dir":
            self._run_dir = event.get("run_dir")

        elif etype == "todos":
            self._todos = event.get("todos") or []

        elif etype == "phase_start":
            subagent = event.get("subagent", "?")
            self._current_phase = {"subagent": subagent, "description": event.get("description", "")}
            self._subagent_bucket(subagent)["calls"] += 1

        elif etype == "phase_end":
            self._current_phase = None
            subagent = event.get("subagent", "?")
            self._subagent_bucket(subagent)["total_seconds"] += float(event.get("elapsed") or 0)

        elif etype == "phase_error":
            self._current_phase = None
            subagent = event.get("subagent", "?")
            bucket = self._subagent_bucket(subagent)
            bucket["total_seconds"] += float(event.get("elapsed") or 0)
            bucket["errors"] += 1

        elif etype == "skill_read":
            skill = event.get("skill")
            if skill:
                self._skill_usage.setdefault(skill, {"reads": 0})["reads"] += 1

        elif etype == "auto_continue":
            self._auto_continue_attempts = event.get("attempt", self._auto_continue_attempts)

        # Unknown event types are ignored rather than raised -- this must
        # never be the reason a real generation run fails; see the same
        # philosophy in `agent/custom_subagents.py`.

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_dir": self._run_dir,
            "todos": list(self._todos),
            "current_phase": self._current_phase,
            "subagent_usage": {k: dict(v) for k, v in self._subagent_usage.items()},
            "skill_usage": {k: dict(v) for k, v in self._skill_usage.items()},
            "auto_continue_attempts": self._auto_continue_attempts,
        }
