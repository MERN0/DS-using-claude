"""
Optional secondary sink for this run's terminal progress lines (see
`agent/progress.py`'s `ProgressLogger` and the handful of `print()` calls in
`agent/runner.py`).

Every one of those calls still prints to stdout unconditionally -- nothing
here changes that, so the CLI (`sys5_agent/main.py`) and a direct `sys5()`
call need zero changes and behave exactly as before. This only adds a
second, optional destination: a caller that wants to *capture* those same
lines (e.g. a web UI polling for a background job's live progress) calls
`set_sink()` with a callback before starting a run, and clears it
(`set_sink(None)`) once the run finishes -- see `frontend/app.py`.

Process-wide, not per-thread or per-run: this only works correctly because
the pipeline currently supports at most one generation running at a time in
a given process (see `frontend/app.py`'s single-job-at-a-time design). If
that ever changes, this needs to become `contextvars`-based instead so each
concurrent run's lines route to its own sink rather than whichever one was
set last.
"""

from __future__ import annotations

from typing import Callable, Optional

_sink: Optional[Callable[[str], None]] = None


def set_sink(sink: Optional[Callable[[str], None]]) -> None:
    global _sink
    _sink = sink


def emit(line: str) -> None:
    print(line, flush=True)
    if _sink is not None:
        _sink(line)
