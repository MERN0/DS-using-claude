"""
Read-only access to one run's intermediate workspace files (discovery.md,
requirements_index.jsonl, clusters.jsonl, resolved/*.md, draft_testcases.jsonl,
qa_report.md, run_summary.json) for the dashboard's "showcase the extracted
data" panels -- see `frontend/app.py`'s `/api/generate/workspace*` routes.

This is the only module that reads these files on the UI's behalf, mirroring
`builders.py`'s "one place touches the real files" pattern.

None of these files have a code-enforced schema anywhere in the pipeline --
they're LLM-authored per the prose instructions in `agent/subagents.py`, not
validated against a pydantic/dataclass model. Every reader here is
defensive: a malformed line becomes a `{"_raw": ..., "_parse_error": ...}`
entry rather than raising, matching the pipeline's own "one bad thing never
fails the whole run" philosophy (see `agent/custom_subagents.py`) -- a
run's real generation result must never be hidden behind a 500 just because
this read-only convenience view choked on a line.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    """Read a `.jsonl` file (one JSON object per line), tolerating blank
    lines and malformed ones. Returns [] if the file doesn't exist yet --
    that's the normal, expected state before that phase has run."""
    if not path.is_file():
        return []
    out: list[dict] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            out.append({"_raw": line, "_parse_error": str(e)})
        else:
            out.append(obj if isinstance(obj, dict) else {"_raw": line, "_parse_error": "not a JSON object"})
        if limit is not None and len(out) >= limit:
            break
    return out


def _resolved_dir(run_dir: Path) -> Path:
    return run_dir / "resolved"


def workspace_manifest(run_dir: Path) -> dict[str, Any]:
    """Which workspace files exist yet, for a UI to know what's worth
    fetching without guessing from run status alone -- a run mid-resolution
    has clusters.jsonl but not draft_testcases.jsonl yet, and that's a
    normal, expected state, not an error."""
    resolved_dir = _resolved_dir(run_dir)
    resolved_cluster_ids = sorted(p.stem for p in resolved_dir.glob("*.md")) if resolved_dir.is_dir() else []
    return {
        "discovery": (run_dir / "discovery.md").is_file(),
        "requirements_index": (run_dir / "requirements_index.jsonl").is_file(),
        "clusters": (run_dir / "clusters.jsonl").is_file(),
        "draft_testcases": (run_dir / "draft_testcases.jsonl").is_file(),
        "qa_report": (run_dir / "qa_report.md").is_file(),
        "run_summary": (run_dir / "run_summary.json").is_file(),
        "resolved_cluster_ids": resolved_cluster_ids,
    }


def read_clusters(run_dir: Path) -> list[dict]:
    """Each cluster from clusters.jsonl, enriched with `requirement_count`
    (a convenience for the UI table -- everything else is passed through
    verbatim, whatever shape the merge-planning agent actually wrote)."""
    clusters = read_jsonl(run_dir / "clusters.jsonl")
    for c in clusters:
        req_ids = c.get("requirement_ids")
        c["requirement_count"] = len(req_ids) if isinstance(req_ids, list) else 0
    return clusters


def read_requirements_index(run_dir: Path, cluster_id: str | None = None) -> list[dict]:
    """Every qualifying requirement, optionally filtered to just the ones
    belonging to one cluster (cross-referenced via clusters.jsonl's own
    requirement_ids list, not anything embedded in the requirement rows
    themselves -- requirements_index.jsonl has no cluster_id field)."""
    requirements = read_jsonl(run_dir / "requirements_index.jsonl")
    if cluster_id is None:
        return requirements

    wanted_ids: set[str] = set()
    for c in read_jsonl(run_dir / "clusters.jsonl"):
        if c.get("cluster_id") == cluster_id:
            req_ids = c.get("requirement_ids")
            if isinstance(req_ids, list):
                wanted_ids.update(str(r) for r in req_ids)
            break

    def _req_id(req: dict) -> str | None:
        for key in ("requirement_id", "id", "req_id"):
            if key in req:
                return str(req[key])
        return None

    return [r for r in requirements if _req_id(r) in wanted_ids]


def read_draft_testcases_enriched(run_dir: Path) -> list[dict]:
    """Every drafted test case, each enriched with a best-effort `_cluster_id`
    / `_check_type` looked up by matching its "Traceability" field's text
    against clusters.jsonl's requirement_ids -- draft_testcases.jsonl has no
    cluster_id field of its own (see agent/subagents.py's
    test_case_drafting_agent), and the Traceability field's exact format is
    free text the drafting agent writes, not a structured list, so this is
    substring matching, not a guaranteed-exact join. A row that matches no
    known requirement ID gets `_cluster_id: None` rather than a guess."""
    testcases = read_jsonl(run_dir / "draft_testcases.jsonl")
    clusters = read_jsonl(run_dir / "clusters.jsonl")

    req_to_cluster: dict[str, tuple[str, str]] = {}
    for c in clusters:
        cluster_id = c.get("cluster_id")
        check_type = c.get("check_type")
        req_ids = c.get("requirement_ids")
        if not cluster_id or not isinstance(req_ids, list):
            continue
        for req_id in req_ids:
            req_to_cluster[str(req_id)] = (cluster_id, check_type)

    for row in testcases:
        traceability = str(row.get("Traceability") or "")
        match = next((req_id for req_id in req_to_cluster if req_id and req_id in traceability), None)
        if match:
            cluster_id, check_type = req_to_cluster[match]
            row["_cluster_id"] = cluster_id
            row["_check_type"] = check_type
        else:
            row["_cluster_id"] = None
            row["_check_type"] = None

    return testcases


def read_resolved_markdown(run_dir: Path, cluster_id: str) -> str | None:
    """`cluster_id` ultimately comes from LLM-authored clusters.jsonl, not a
    validated name -- resolve it against resolved_dir and refuse anything
    that would land outside it (e.g. a `cluster_id` containing `../`)
    rather than trusting it's always the simple "c1"-style token the
    prompts ask for."""
    resolved_dir = _resolved_dir(run_dir).resolve()
    candidate = (resolved_dir / f"{cluster_id}.md").resolve()
    if candidate != resolved_dir and resolved_dir not in candidate.parents:
        return None
    return candidate.read_text(encoding="utf-8") if candidate.is_file() else None


def read_qa_report(run_dir: Path) -> str | None:
    path = run_dir / "qa_report.md"
    return path.read_text(encoding="utf-8") if path.is_file() else None


def read_run_summary(run_dir: Path) -> dict | None:
    path = run_dir / "run_summary.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"_raw": path.read_text(encoding="utf-8"), "_parse_error": str(e)}
    return data if isinstance(data, dict) else {"_raw": str(data), "_parse_error": "not a JSON object"}
