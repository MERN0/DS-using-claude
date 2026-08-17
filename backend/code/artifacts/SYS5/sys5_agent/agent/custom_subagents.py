"""
Loads client-specific custom subagents from clients/<client>/subagents/*.md,
appending to the fixed six subagents `build_subagents()` already returns
(see `agent/subagents.py`).

Custom subagent file format (one Markdown file per subagent, mirroring the
SKILL.md convention already used throughout this codebase -- YAML
frontmatter + Markdown body -- rather than inventing a new one):

    ---
    name: extra-safety-checks-agent
    description: One sentence the orchestrator reads to decide whether to
      delegate to this subagent, and when.
    tools: [search_sheet, read_sheet_range]
    skills: [domain-knowledge]
    ---

    The subagent's own system prompt, as plain Markdown.

These are always ADDITIVE, never a replacement for the fixed six-phase
pipeline (discovery -> extraction -> merge planning -> resolution ->
drafting -> QA) -- a malformed, missing, or partially-invalid custom
subagent file is never a reason to fail a whole run, so every validation
error here is logged (printed, so it shows up the same way
`agent/progress.py`'s live logging does) and that one file is skipped
rather than raised.

The dashboard at `frontend/` (repo root, a sibling of `backend/`) is what
actually writes these files today, but the format is deliberately
hand-editable too -- nothing here depends on how a file was created.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from sys5_agent.config import settings
from sys5_agent.tools.excel_tools import build_read_only_tools

# Appended to every custom subagent's own system_prompt at *load* time, not
# stored in the authored file -- this way the reminder can't go stale or be
# accidentally edited out, and the UI doesn't have to keep a second copy of
# this text in sync with this one. Mirrors the same non-negotiable rules
# `agent/prompts.py` gives the orchestrator and the six built-in subagents.
_CONTRACT_REMINDER = (
    "\n\n---\n\n"
    "You are a client-specific extension to the standard SYS2->SYS5 "
    "pipeline, not a replacement for any of its six fixed phases (see the "
    "orchestrator's own phase checklist). The same non-negotiable output "
    "contract applies to anything you write into the run workspace or hand "
    "back to whoever called you: never invent a signal, command, "
    "parameter, or value -- everything traces back to what a resolution "
    "subagent actually confirmed, referenced by its alias, never a raw "
    "ID/address. If you write any Test Steps/Expected Result content, "
    "`SET` uses `=` and `VERIFY` uses `==` -- never a comma, never the "
    'word "to"/"is"/"equals". Test Case ID is always assigned '
    f"automatically as `{settings.TEST_CASE_ID_PREFIX}<n>` by "
    "write_output_workbook -- never assign one yourself. Persist detailed "
    "findings to a file in the run workspace and return only a short "
    "summary to whoever delegated to you."
)

# Public: this is the single definition of the file format (frontmatter
# block + body) -- frontend/builders.py reuses it directly so authoring/
# editing through the UI can never drift from what this loader actually
# accepts.
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def _parse_subagent_file(path: Path) -> dict[str, Any] | None:
    """Parse one custom-subagent Markdown file.

    Returns None (after printing why) instead of raising for anything
    malformed -- see module docstring on why one bad file must never take
    down a whole run.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[custom-subagents] skipping {path.name}: could not read file: {e}", flush=True)
        return None

    match = FRONTMATTER_RE.match(text)
    if not match:
        print(f"[custom-subagents] skipping {path.name}: no '---' YAML frontmatter block found", flush=True)
        return None

    try:
        front = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        print(f"[custom-subagents] skipping {path.name}: invalid frontmatter YAML: {e}", flush=True)
        return None

    if not isinstance(front, dict):
        print(f"[custom-subagents] skipping {path.name}: frontmatter is not a mapping", flush=True)
        return None

    name = str(front.get("name") or "").strip()
    description = str(front.get("description") or "").strip()
    body = match.group(2).strip()

    if not name or not description or not body:
        print(f"[custom-subagents] skipping {path.name}: missing 'name', 'description', or a body", flush=True)
        return None

    tools_field = front.get("tools") or []
    skills_field = front.get("skills") or []
    if not isinstance(tools_field, list) or not isinstance(skills_field, list):
        print(f"[custom-subagents] skipping {path.name}: 'tools' and 'skills' must be lists", flush=True)
        return None

    return {
        "name": name,
        "description": description,
        "system_prompt": body + _CONTRACT_REMINDER,
        "tool_names": [str(t).strip() for t in tools_field],
        "skill_names": [str(s).strip() for s in skills_field],
    }


def load_custom_subagents(client: str, input_root: Path, run_dir: Path, extra_tools: list | None = None) -> list[dict]:
    """Load every `clients/<client>/subagents/*.md` file into subagent dicts,
    ready to append to `build_subagents(input_root)`'s return value.

    `input_root` resolves each requested tool name against this run's real
    tool instances (see `tools/excel_tools.build_read_only_tools`); an
    unknown tool name is dropped (with a printed warning), not treated as a
    reason to skip the whole subagent. `extra_tools`, if given (see
    `tools/mcp_tools.py`), are added to that same by-name lookup -- a
    client can request one of these by name exactly like a built-in excel
    tool, no separate mechanism. `run_dir` is used the same way for skill
    names: only a skill that's actually present under `run_dir/skills/`
    (i.e. one of the baseline/domain/client skills this run already
    layered in -- see `agent/build.py`) is kept, since a reference to a
    skill that was never copied into this run's workspace would be a dead
    reference.
    """
    if client == settings.DEFAULT_CLIENT_DIR_NAME:
        return []
    subagents_dir = settings.client_dir(client) / "subagents"
    if not subagents_dir.is_dir():
        return []

    tools_by_name = {t.name: t for t in build_read_only_tools(input_root)}
    for t in extra_tools or []:
        tools_by_name[t.name] = t
    run_skills_dir = run_dir / "skills"

    out: list[dict] = []
    seen_names: set[str] = set()
    for path in sorted(subagents_dir.glob("*.md")):
        parsed = _parse_subagent_file(path)
        if parsed is None:
            continue

        if parsed["name"] in seen_names:
            print(
                f"[custom-subagents] skipping {path.name}: duplicate subagent name '{parsed['name']}'",
                flush=True,
            )
            continue

        tools = []
        for tool_name in parsed["tool_names"]:
            tool_obj = tools_by_name.get(tool_name)
            if tool_obj is None:
                print(
                    f"[custom-subagents] {path.name}: unknown tool '{tool_name}' -- dropping it "
                    f"(available: {sorted(tools_by_name)})",
                    flush=True,
                )
                continue
            tools.append(tool_obj)

        skills = []
        for skill_name in parsed["skill_names"]:
            if not (run_skills_dir / skill_name).is_dir():
                print(
                    f"[custom-subagents] {path.name}: skill '{skill_name}' isn't available this run -- dropping it",
                    flush=True,
                )
                continue
            skills.append(skill_name)

        out.append(
            {
                "name": parsed["name"],
                "description": parsed["description"],
                "system_prompt": parsed["system_prompt"],
                "tools": tools,
                "skills": skills,
            }
        )
        seen_names.add(parsed["name"])
        print(f"[custom-subagents] loaded '{parsed['name']}' from {path.name}", flush=True)

    return out
