"""
Terminal progress logging for a run.

`agent.invoke(...)` is one blocking call from the caller's point of view --
without this, nothing is printed between "Starting agent run..." and the
final result, even though the orchestrator may spend many minutes
delegating to subagents that each make dozens of tool calls. This attaches
a `BaseCallbackHandler` to that call instead of switching to streaming: tool
calls fire callbacks synchronously as they happen, at every nesting level
(deepagents' own `task` tool explicitly forwards the parent's callbacks down
into each subagent invocation), so a handler registered once on the
top-level `agent.invoke(...)` config sees every tool call made anywhere in
the run -- the orchestrator's own, and every subagent's -- without needing
to restructure the call into a stream loop.

`task` calls (an orchestrator delegating to a subagent) are logged as a
named phase transition (">>> Delegating to discovery-agent: ..."); every
other tool call is logged as a single compact line. Lines go through
`agent/logsink.py`'s `emit()` rather than a bare `print()` -- every line
still always prints to stdout (matching how the CLI already reports
progress, see `sys5_agent/main.py`), but this also lets a caller like the
web UI (`frontend/app.py`) capture the same lines for a live-progress
display, without needing to restructure this into a stream loop.

Alongside those free-text lines, this also emits STRUCTURED events through
`agent/run_events.py` for the same tool calls -- a `write_todos` call
carries the orchestrator's full current todo list, a `task` call marks
which subagent is now the "current phase" (and its wall-clock duration once
it ends), and a `read_file` call whose path starts with `skills/` marks
that skill as read -- so a caller can build a live todo checklist / usage
panel without parsing log text. See `run_events.RunStateAggregator`.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from sys5_agent.agent import logsink, run_events

_MAX_LINE = 160
_SKILLS_PREFIX = "skills/"


def _truncate(text: str, limit: int = _MAX_LINE) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _timestamp() -> str:
    return time.strftime("%H:%M:%S")


class ProgressLogger(BaseCallbackHandler):
    """Prints one line per tool call start/end/error, across the orchestrator
    and every subagent it delegates to, so a long run isn't silent."""

    def __init__(self) -> None:
        self._task_calls: dict[UUID, tuple[str, float]] = {}
        self._other_calls: dict[UUID, float] = {}

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        name = (serialized or {}).get("name") or "tool"
        args = inputs if inputs is not None else {"input": input_str}

        if name == "task":
            subagent_type = args.get("subagent_type", "?")
            description = args.get("description", "")
            self._task_calls[run_id] = (subagent_type, time.monotonic())
            logsink.emit(f"[{_timestamp()}] >>> delegating to {subagent_type}: {_truncate(description)}")
            run_events.emit({"type": "phase_start", "subagent": subagent_type, "description": description})
            return

        if name == "write_todos":
            # Always the full replacement list, not a diff -- see
            # `langchain.agents.middleware.todo.write_todos`'s own
            # implementation, which unconditionally overwrites state.
            run_events.emit({"type": "todos", "todos": args.get("todos") or []})
        elif name == "read_file":
            file_path = str(args.get("file_path") or "")
            if file_path.startswith(_SKILLS_PREFIX):
                # "skills/<name>/SKILL.md" or "skills/<name>" -- the segment
                # right after the prefix is the skill name either way.
                skill_name = file_path[len(_SKILLS_PREFIX) :].split("/", 1)[0]
                if skill_name:
                    run_events.emit({"type": "skill_read", "skill": skill_name})

        self._other_calls[run_id] = time.monotonic()
        logsink.emit(f"[{_timestamp()}]     {name}({_truncate(args)})")

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        task_entry = self._task_calls.pop(run_id, None)
        if task_entry is not None:
            subagent_type, started_at = task_entry
            elapsed = time.monotonic() - started_at
            summary = getattr(output, "content", output)
            logsink.emit(f"[{_timestamp()}] <<< {subagent_type} finished in {elapsed:.1f}s: {_truncate(summary)}")
            run_events.emit({"type": "phase_end", "subagent": subagent_type, "elapsed": elapsed})
            return
        self._other_calls.pop(run_id, None)

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        task_entry = self._task_calls.pop(run_id, None)
        if task_entry is not None:
            subagent_type, started_at = task_entry
            elapsed = time.monotonic() - started_at
            logsink.emit(
                f"[{_timestamp()}] !!! {subagent_type} FAILED after {elapsed:.1f}s: "
                f"{type(error).__name__}: {_truncate(error)}"
            )
            run_events.emit(
                {
                    "type": "phase_error",
                    "subagent": subagent_type,
                    "elapsed": elapsed,
                    "error": f"{type(error).__name__}: {_truncate(error)}",
                }
            )
            return
        self._other_calls.pop(run_id, None)
        logsink.emit(f"[{_timestamp()}] !!! tool error: {type(error).__name__}: {_truncate(error)}")
