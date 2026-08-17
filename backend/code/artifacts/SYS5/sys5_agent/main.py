"""
CLI entry point for SYS2 -> SYS5 test case generation.

Usage:
    python main.py --client acme --domain bcm --input-dir /path/to/client/data \\
        --requirements-file SYS2_Requirements.xlsx \\
        [--output-path output/acme_SYS5.xlsx]

--domain is passed once at the start of a run and stays constant for the
whole cycle; it loads that automotive domain's detailed knowledge (typical
ECUs/modules, signal/command naming conventions, buses, requirement/test
patterns) as an on-demand skill alongside the standard rules.

This file only wires CLI args to `agent.runner.run_pipeline` and reports the
result -- the backend entry point (`backend/code/artifacts/SYS5/sys5.py`)
calls the same `run_pipeline` function, so this stays the thin CLI wrapper
around one shared code path rather than a second implementation. All
tunables (model endpoint, chunk sizes, output columns, qualification
markers, retry limits) live in config/settings.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Internal modules are imported as `sys5_agent.*` (see agent/build.py,
# agent/prompts.py, agent/subagents.py, agent/runner.py, tools/excel_tools.py)
# so that a single import style works whether this is run as
# `python -m sys5_agent.main` or `python main.py`/`python sys5_agent/main.py`
# directly. The latter forms only put this file's own directory on
# sys.path, not its parent, so `import sys5_agent` would otherwise fail --
# make sure the package's parent directory is importable before pulling in
# any sys5_agent.* module.
_PACKAGE_PARENT = Path(__file__).resolve().parent.parent
if str(_PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PARENT))

from sys5_agent.agent.runner import run_pipeline  # noqa: E402
from sys5_agent.config import settings  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client",
        default=settings.DEFAULT_CLIENT_DIR_NAME,
        help=f"Client name, matching a clients/<name> directory. "
        f"Defaults to '{settings.DEFAULT_CLIENT_DIR_NAME}' (generic rules only).",
    )
    parser.add_argument(
        "--domain",
        required=True,
        choices=sorted(settings.DOMAINS) + sorted(settings.DOMAIN_ALIASES),
        help=(
            "Automotive domain for this run, constant for the whole cycle "
            f"(loads that domain's knowledge as a skill). One of: "
            f"{', '.join(settings.DOMAINS)}."
        ),
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing the requirements file and all supporting workbooks. "
        "The agent can read only inside this directory.",
    )
    parser.add_argument(
        "--requirements-file",
        required=True,
        help="File name (within --input-dir) of the SYS2 requirements workbook.",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Where to write the generated SYS5 .xlsx. Defaults to output/<client>_SYS5_<run-id>.xlsx. "
        "The agent can write only to this exact file.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    input_dir = Path(args.input_dir).resolve()
    requirements_path = input_dir / args.requirements_file
    if not requirements_path.is_file():
        print(f"ERROR: requirements file not found: {requirements_path}", file=sys.stderr)
        return 2

    try:
        client_dir = settings.client_dir(args.client)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if args.client != settings.DEFAULT_CLIENT_DIR_NAME and not client_dir.is_dir():
        print(
            f"WARNING: clients/{args.client} does not exist yet -- proceeding with "
            f"baseline ('{settings.DEFAULT_CLIENT_DIR_NAME}') rules only.",
            file=sys.stderr,
        )

    domain = settings.normalize_domain(args.domain)
    if not (settings.domain_dir(domain) / "skills" / "domain-knowledge").is_dir():
        print(
            f"WARNING: domains/{domain} has no domain-knowledge skill yet -- "
            "proceeding without domain-specific knowledge.",
            file=sys.stderr,
        )

    if args.output_path:
        output_path = Path(args.output_path)
    else:
        # The output path must be fixed before the agent is built (it's
        # sandboxed to it -- see build_agent), so the default name uses our
        # own timestamp rather than the run workspace's (which doesn't
        # exist yet at this point).
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        output_path = settings.OUTPUT_DIR / f"{args.client}_SYS5_{stamp}.xlsx"
    output_path = output_path.resolve()

    task_message_lines = [
        f"Client: {args.client}",
        f"Domain: {domain} ({settings.DOMAIN_LABELS.get(domain, domain)})",
        f"Requirements file name: {args.requirements_file}",
        "Input files: call list_input_files() (no arguments) via the "
        "discovery-agent to enumerate them -- this run's input directory is "
        "already fixed, there is no path to look up or pass in.",
        f"Output path for the final workbook: {output_path}",
    ]

    print("Starting agent run (this can take a while for large requirements files)...")

    result = run_pipeline(
        client=args.client,
        domain=domain,
        input_dir=input_dir,
        output_path=output_path,
        context_lines=task_message_lines,
    )

    print(f"Run workspace: {result['run_dir']}")

    if result["summary"] is not None:
        print("\n=== Run summary ===")
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    else:
        print(
            "\nWARNING: agent did not write run_summary.json -- inspect the run "
            f"workspace at {result['run_dir']} for what happened.",
            file=sys.stderr,
        )

    if result["output_exists"]:
        print(f"\nOutput workbook: {result['output_path']}")
        return 0

    print(f"\nERROR: expected output workbook not found at {result['output_path']}", file=sys.stderr)
    print(f"Agent's final message: {result['final_message'] or '(no final message)'}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
