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
from typing import Any, Optional

from sys5_agent.agent.build import build_agent


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
    QA issues) is never raised -- it's reported in the returned dict.
    """
    agent, run_dir = build_agent(client, domain, input_dir, output_path)

    task_message = (
        "\n".join(context_lines)
        + "\n\nGenerate the SYS5 test case workbook for this run now, "
        "following your system instructions."
    )

    result = agent.invoke(
        {"messages": [{"role": "user", "content": task_message}]},
        config={"configurable": {"thread_id": run_dir.name}, "recursion_limit": 1000},
    )

    summary_path = run_dir / "run_summary.json"
    summary: Optional[dict] = None
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))

    final_message = None
    if result.get("messages"):
        final_message = result["messages"][-1].content

    return {
        "run_dir": run_dir,
        "output_path": output_path,
        "output_exists": output_path.is_file(),
        "summary": summary,
        "final_message": final_message,
    }
