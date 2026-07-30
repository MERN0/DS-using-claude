"""
Backend entry point for SYS2 -> SYS5 automotive test case generation.

The backend calls `sys5(...)` directly (no CLI / subprocess involved) with
per-run parameters; everything else -- model, run workspace, layered
client/domain rules, subagents, retries -- is handled by the `sys5_agent`
package this function delegates to. This module intentionally contains no
pipeline/domain logic of its own: it validates the backend's parameters,
maps them onto `sys5_agent`'s (client, domain, input_dir, output_path)
shape, and calls the same `run_pipeline` the CLI (`sys5_agent/main.py`)
uses, so there is exactly one implementation of the generation cycle.

## Sandboxing

The agent this call builds can read only inside `input_folder_path` and can
write only to the single output file computed from `output_folder_path` --
see `sys5_agent.agent.build.build_agent` and `sys5_agent.tools.excel_tools`
for how that's enforced (not by convention -- the tools are physically
incapable of resolving a path outside those directories). No other
directory on disk is reachable from the agent's tools.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# This file lives four levels below the repo root
# (backend/code/artifacts/SYS5/sys5.py), which is not on sys.path by
# default -- add the repo root so `import sys5_agent` works regardless of
# how/where the backend imports this module from.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sys5_agent.agent.runner import run_pipeline  # noqa: E402
from sys5_agent.config import settings  # noqa: E402

_VERSION_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def sys5(
    domain: str,
    output_format: str,
    project_name: str,
    username: str,
    current_version: str,
    input_folder_path: str,
    output_folder_path: str,
    requirement_filename: str,
) -> dict[str, Any]:
    """Run one SYS2 -> SYS5 generation cycle for the backend.

    Args:
        domain: Automotive domain for this run, constant for the whole
            cycle -- one of `settings.DOMAINS` (`bcm`, `ivi`, `ev`,
            `powertrain`, `adas`, `chassis`, `telematics`; `chasis` is
            accepted as an alias for `chassis`). Selects the
            `domain-knowledge` skill loaded alongside the standard rules.
        output_format: File format for the generated workbook. Only
            `"xlsx"` is currently implemented (see
            `settings.SUPPORTED_OUTPUT_FORMATS`).
        project_name: Identifies this project the way the CLI's `--client`
            does -- maps to `clients/<project_name>/` for any project-
            specific rule/skill overrides layered on top of the baseline
            rules (see `clients/_default/`). A project with no such
            directory yet still runs fine on the baseline rules alone.
        username: Who requested this run. Not used for any pipeline
            decision -- carried into the task context purely for
            provenance/traceability in the run's own records.
        current_version: Version tag for the requirements being processed
            (e.g. a SYS2 document revision). Used to name the output file
            and carried into the task context; not otherwise interpreted.
        input_folder_path: Directory containing `requirement_filename` and
            every supporting workbook (signal list, command list, etc.).
            The agent can read only inside this directory -- nothing else
            on disk is reachable from its tools.
        output_folder_path: Directory the generated workbook is written
            into. Created if it doesn't exist. The agent can write only to
            the single computed output file inside it -- it is never given
            a choice of filename or destination.
        requirement_filename: File name (inside `input_folder_path`) of the
            SYS2 requirements workbook.

    Returns:
        dict with:
            - "success": bool -- whether the output workbook was written.
            - "output_path": str -- where it was (or would have been)
              written.
            - "run_dir": str -- this run's workspace, for inspecting
              intermediate files (discovery.md, requirements_index.jsonl,
              clusters.jsonl, resolved/*.md, draft_testcases.jsonl,
              qa_report.md, run_summary.json) if something needs debugging.
            - "summary": dict | None -- the parsed run_summary.json (counts,
              traceability coverage, critical_failures, etc.), or None if
              the agent never wrote one (treat that as a failure signal).
            - "final_message": str | None -- the orchestrator's last
              message, useful when "success" is False and there's no
              summary to explain why.

    Raises:
        FileNotFoundError: `input_folder_path` doesn't exist, or
            `requirement_filename` isn't inside it.
        ValueError: `domain`, `output_format`, or `project_name` is
            invalid.
    """
    input_dir = Path(input_folder_path).resolve()
    if not input_dir.is_dir():
        raise FileNotFoundError(f"input_folder_path does not exist or is not a directory: {input_dir}")

    requirements_path = input_dir / requirement_filename
    if not requirements_path.is_file():
        raise FileNotFoundError(f"requirement_filename not found inside input_folder_path: {requirements_path}")

    normalized_domain = settings.normalize_domain(domain)
    if normalized_domain not in settings.DOMAINS:
        raise ValueError(
            f"Unsupported domain {domain!r}. Must be one of: {settings.DOMAINS} "
            f"(aliases accepted: {sorted(settings.DOMAIN_ALIASES)})."
        )

    normalized_format = str(output_format).strip().lower().lstrip(".")
    if normalized_format not in settings.SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(
            f"Unsupported output_format {output_format!r}. Must be one of: {settings.SUPPORTED_OUTPUT_FORMATS}."
        )

    # Raises ValueError for a project_name that isn't a safe path segment
    # (e.g. contains '/' or '..') before it ever reaches a Path join.
    settings.client_dir(project_name)

    output_dir = Path(output_folder_path).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_version = _VERSION_SAFE_RE.sub("_", str(current_version).strip()) or "v0"
    output_path = output_dir / f"{project_name}_SYS5_{safe_version}.{normalized_format}"

    context_lines = [
        f"Project: {project_name}",
        f"Requested by: {username}",
        f"Requirements version: {current_version}",
        f"Domain: {normalized_domain} ({settings.DOMAIN_LABELS.get(normalized_domain, normalized_domain)})",
        f"Input directory: {input_dir}",
        f"Requirements file name: {requirement_filename}",
        f"Output path for the final workbook: {output_path}",
    ]

    result = run_pipeline(
        client=project_name,
        domain=normalized_domain,
        input_dir=input_dir,
        output_path=output_path,
        context_lines=context_lines,
    )

    return {
        "success": result["output_exists"],
        "output_path": str(result["output_path"]),
        "run_dir": str(result["run_dir"]),
        "summary": result["summary"],
        "final_message": result["final_message"],
    }
