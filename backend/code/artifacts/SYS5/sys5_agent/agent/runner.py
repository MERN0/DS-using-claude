"""
Shared "build the agent, run one cycle, report back" logic.

Both the CLI (`sys5_agent/main.py`) and the backend entry point
(`backend/code/artifacts/SYS5/sys5.py`) call `run_pipeline` rather than each
re-implementing agent invocation / run-summary reading -- this is the one
place that turns (client, domain, input_dir, output_path, task context)
into an actual generation run and a structured result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sys5_agent.agent import logsink
from sys5_agent.agent.build import build_agent
from sys5_agent.agent.progress import ProgressLogger
from sys5_agent.config import settings

_CONTINUE_NUDGE = (
    "You stopped without finishing -- run_summary.json does not exist yet in "
    "the run workspace, which means the pipeline is not actually done "
    "regardless of what your last message said. Check your todo list and "
    "the workspace files you've already written (discovery.md, "
    "requirements_index.jsonl, clusters.jsonl, resolved/*.md, "
    "draft_testcases.jsonl, qa_report.md if present), then continue exactly "
    "where you left off through the remaining phases until run_summary.json "
    "is written. Take the next concrete action (delegate to a subagent, or "
    "call write_output_workbook / write run_summary.json if everything else "
    "is already done) -- do not just describe status again."
)


def run_pipeline(
    *,
    client: str,
    domain: str,
    input_dir: Path,
    output_path: Path,
    context_lines: list[str],
) -> dict[str, Any]:
    """Build and run one SYS2 -> SYS5 generation cycle.

    `context_lines` are joined one-per-line at the top of the task message
    handed to the orchestrator (e.g. "Client: acme", "Domain: bcm (...)",
    "Requirements file name: ..."). This function never inspects their
    content -- it's just how the caller passes per-run identifying context
    into the agent's first turn.

    `input_dir` and `output_path` are forwarded to `build_agent`, which
    sandboxes every excel tool to them (see `agent/build.py` and
    `tools/excel_tools.py`) -- the agent cannot read outside `input_dir` or
    write anywhere but `output_path`.

    Returns a dict:
        {"run_dir": Path, "output_path": Path, "output_exists": bool,
         "summary": dict | None, "final_message": str | None}

    Raises only for a build-time configuration error (invalid client/domain,
    missing input_dir -- see `build_agent`), which is the caller's bug to
    fix before a run even starts. A *generation* failure (missing output,
    QA issues, or the agent run itself raising -- e.g. a `deepagents`/model
    provider error mid-run) is never raised -- it's reported in the returned
    dict, with `final_message` carrying the error detail when there's no
    orchestrator message to fall back on. A single bad tool call (or worse,
    a bug in a dependency) losing one run's progress is one thing; letting
    that same exception propagate and take down the caller's whole process
    is a much bigger one, and there's no reason the latter has to follow
    from the former.

    Prints one line per tool call (including every subagent's own calls) to
    stdout as the run progresses -- see `agent/progress.py` -- since
    `agent.invoke(...)` would otherwise be silent for the run's entire
    duration. Every one of those lines (and this function's own) goes
    through `agent/logsink.py`, so a caller that registered a sink there
    before calling this (e.g. `frontend/app.py`, for a live-progress UI)
    receives them too, without affecting the CLI's plain stdout output.

    `deepagents`' agent loop ends the moment the orchestrator's latest
    message has no tool call in it -- normally that only happens once
    `run_summary.json` has actually been written (the orchestrator's own
    last step), but nothing stops a model from just stopping early instead
    (e.g. replying with a chatty status update mid-pipeline). Since
    `build_agent` gives the returned agent an in-memory checkpointer, this
    function can tell the difference -- `run_summary.json` existing is the
    orchestrator's own definition of "done" -- and if it's missing after an
    otherwise-successful `invoke()`, automatically continues the *same*
    conversation (full history intact, nothing re-explained) with a short
    nudge, up to `settings.MAX_AUTO_CONTINUE_TURNS` times, before giving up
    and reporting the run as genuinely incomplete.
    """
    agent, run_dir = build_agent(client, domain, input_dir, output_path)

    # Record whether a file already sits at `output_path` (and, if so, when
    # it was last written) *before* the agent runs. A bare `is_file()` check
    # afterward can't tell "this run just wrote it" apart from "a stale file
    # from an earlier run of the same project+version happened to be sitting
    # there the whole time and this run never touched it" -- and the latter
    # used to get reported as a success purely because something with the
    # right name existed on disk.
    pre_run_mtime = output_path.stat().st_mtime if output_path.exists() else None

    task_message = (
        "\n".join(context_lines) + "\n\nGenerate the SYS5 test case workbook for this run now, "
        "following your system instructions."
    )

    logsink.emit(f"Run workspace: {run_dir}")

    invoke_config = {
        "configurable": {"thread_id": run_dir.name},
        "recursion_limit": 1000,
        "callbacks": [ProgressLogger()],
    }
    summary_path = run_dir / "run_summary.json"

    crash_message: str | None = None
    result: dict[str, Any] = {}
    next_message = task_message
    attempt = 0
    while True:
        try:
            result = agent.invoke({"messages": [{"role": "user", "content": next_message}]}, config=invoke_config)
        except Exception as e:  # noqa: BLE001 -- deliberately broad, see docstring
            # A run that gets this far has usually already burned real time
            # and money (many model calls deep into discovery/extraction/
            # resolution) -- losing that is bad enough without also crashing
            # whatever process called `run_pipeline` (the backend service,
            # the CLI). Whatever actually broke (a dependency bug, a
            # provider-side rejection, a tool escaping in a way nothing here
            # caught) is reported the same way any other generation failure
            # is: in the returned dict, never by propagating. Unlike an
            # incomplete-but-not-crashed run below, a crash is not
            # auto-retried here -- that's a different failure mode, and
            # blindly re-invoking into whatever just broke is more likely to
            # repeat it than fix it.
            crash_message = f"Agent run raised {type(e).__name__}: {e}"
            logsink.emit(f"[{run_dir.name}] !!! run crashed: {crash_message}")
            break

        if summary_path.is_file():
            break

        attempt += 1
        if attempt > settings.MAX_AUTO_CONTINUE_TURNS:
            logsink.emit(
                f"[{run_dir.name}] !!! giving up after {attempt - 1} auto-continue "
                "attempt(s) -- run_summary.json was never written."
            )
            break

        logsink.emit(
            f"[{run_dir.name}] ... orchestrator stopped before finishing (no "
            f"run_summary.json yet) -- auto-continuing "
            f"(attempt {attempt}/{settings.MAX_AUTO_CONTINUE_TURNS})"
        )
        next_message = _CONTINUE_NUDGE

    summary: dict | None = None
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    final_message = crash_message
    if final_message is None and result.get("messages"):
        final_message = result["messages"][-1].content

    output_written_this_run = output_path.is_file() and (
        pre_run_mtime is None or output_path.stat().st_mtime != pre_run_mtime
    )

    return {
        "run_dir": run_dir,
        "output_path": output_path,
        "output_exists": output_written_this_run,
        "summary": summary,
        "final_message": final_message,
    }
