"""
All read/write/validate logic for a client's customizations: memory rules,
skill overrides, and custom subagents. This is the ONLY module that touches
the real `clients/<name>/` directory tree on behalf of the UI -- `app.py`'s
FastAPI routes call these functions, never write files directly, so every
format guarantee the pipeline itself relies on (see
`sys5_agent/agent/build.py` and `sys5_agent/agent/custom_subagents.py`) is
enforced in exactly one place.

Nothing here talks to an LLM or runs a generation -- this UI only authors
the files a future `sys5()`/CLI run will pick up (see `README.md` in this
directory).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# This file lives in frontend/ at the repo root, a sibling of backend/ --
# not nested under the SYS5 package -- so the path to sys5_agent has to be
# spelled out rather than assumed to be this file's own parent directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SYS5_DIR = _REPO_ROOT / "backend" / "code" / "artifacts" / "SYS5"
if str(_SYS5_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS5_DIR))

import yaml  # noqa: E402
from sys5_agent.agent.custom_subagents import FRONTMATTER_RE  # noqa: E402
from sys5_agent.agent.subagents import build_subagents  # noqa: E402
from sys5_agent.config import settings  # noqa: E402
from sys5_agent.tools.excel_tools import build_read_only_tools  # noqa: E402
from sys5_agent.tools.mcp_tools import available_mcp_tool_names  # noqa: E402


class ValidationError(ValueError):
    """Raised for any input the pipeline itself would refuse to load --
    always caught by app.py and turned into a 4xx JSON error, never a
    500."""


# ---------------------------------------------------------------------------
# Reference data the dashboard shows the user (picklists, explanatory
# labels) -- derived from the real implementations rather than duplicated
# by hand, so this can never drift out of sync with what the pipeline
# actually supports.
# ---------------------------------------------------------------------------


def _first_sentence(docstring: str) -> str:
    first_line = docstring.strip().splitlines()[0].strip()
    return first_line


def available_tools() -> dict[str, str]:
    """{tool_name: one-line description}: the 5 sandboxed excel tools
    (straight from the real tool objects, see
    `tools/excel_tools.build_read_only_tools` -- the path used to build
    them doesn't need to exist, only their names/docstrings are read) plus
    the curated MCP tools (see `tools/mcp_tools.py`). The MCP names are
    always listed here regardless of whether `MCP_ENABLED` is actually on
    for a real run -- a client can see and select them either way; only an
    actual generation needs the feature turned on to have them for real."""
    tools = build_read_only_tools(Path("/__ui_reference_only__"))
    out = {t.name: _first_sentence(t.description) for t in tools}
    out.update(available_mcp_tool_names())
    return out


def built_in_subagents() -> list[dict]:
    """[{"name", "description"}, ...] for the six fixed subagents every run
    always includes (see `agent/subagents.py`) -- shown to the user as
    read-only reference so a custom subagent isn't a mystery addition to an
    invisible pipeline. The path doesn't need to exist, same as
    `available_tools()`: only names/descriptions are read, no file access
    happens at construction time."""
    subagents = build_subagents(Path("/__ui_reference_only__"))
    return [{"name": s["name"], "description": s["description"]} for s in subagents]


# The four baseline skills every run loads, plus a client-scoped override of
# domain-knowledge (client tier wins over domain tier -- see
# agent/build.py's `_copy_layered_skills` layering order). These are the
# only skill names any of the six built-in subagents ever actually load, so
# they're the only skill names worth letting a user override here.
OVERRIDABLE_SKILLS: dict[str, str] = {
    "writing-style": (
        "Phrasing, the fixed 1./2./3. numbering, and the mandatory "
        "SET/WAIT/VERIFY (=/==) syntax used when drafting test cases."
    ),
    "output-format": (
        "The canonical definition of all 13 output columns and what counts as a structurally complete row."
    ),
    "resolution-playbook": (
        "How to search the client's supporting documents (signal list, "
        "command list, etc.) for exact signal/command names."
    ),
    "merging-strategy": ("How to decide which requirements collapse into one test case versus stay separate."),
    "domain-knowledge": (
        "This client's automotive domain knowledge (ECUs, signal/command "
        "naming, common patterns). Careful: this REPLACES the standard "
        "domain's knowledge for this client, it doesn't add to it."
    ),
}


def known_skill_names(client: str) -> list[str]:
    """Every skill name a custom subagent for this client could plausibly
    load: the 4 baseline names, domain-knowledge, and any skill this
    client has already overridden under its own directory."""
    names = set(OVERRIDABLE_SKILLS)
    names.update(list_client_skill_overrides(client))
    return sorted(names)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


def validate_client_name(name: str) -> str:
    try:
        settings.client_dir(name)
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return name.strip()


def validate_new_client_name(name: str) -> str:
    """Stricter check for *creating* a new project (see
    `settings.validate_kebab_name`) -- used only by the "create a
    project" flow, not by `validate_client_name` (which also validates a
    reference to a possibly pre-existing client, e.g. before starting a
    generation, and must keep accepting whatever's already there rather
    than retroactively rejecting it)."""
    try:
        return settings.validate_kebab_name(name, "project name")
    except ValueError as e:
        raise ValidationError(str(e)) from e


def list_clients() -> list[str]:
    if not settings.CLIENTS_DIR.is_dir():
        return []
    return sorted(
        p.name for p in settings.CLIENTS_DIR.iterdir() if p.is_dir() and p.name != settings.DEFAULT_CLIENT_DIR_NAME
    )


# ---------------------------------------------------------------------------
# Memory (clients/<name>/memory/AGENTS.md)
# ---------------------------------------------------------------------------


def read_baseline_memory() -> str:
    """The standing rules every run already loads before any client-specific
    addition (`clients/_default/memory/AGENTS.md`) -- read-only reference so
    the dashboard's (empty-by-default) client memory box isn't mistaken for
    "no rules exist yet"; see `agent/build.py`'s `_write_layered_memory`,
    which concatenates this with the client's own file, never replaces it."""
    path = settings.default_client_dir() / "memory" / "AGENTS.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def read_client_memory(client: str) -> str:
    path = settings.client_dir(client) / "memory" / "AGENTS.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def write_client_memory(client: str, text: str) -> Path:
    """Overwrites clients/<client>/memory/AGENTS.md with `text` verbatim.

    Callers building an "append" experience should read the current
    content first (`read_client_memory`) and pass back the combined text --
    this function itself always replaces, so there's exactly one code path
    for both "start a new rule file" and "add to an existing one".
    """
    text = text.strip()
    if not text:
        raise ValidationError("Memory rule text can't be empty.")
    path = settings.client_dir(client) / "memory" / "AGENTS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def delete_client_memory(client: str) -> bool:
    path = settings.client_dir(client) / "memory" / "AGENTS.md"
    if path.is_file():
        path.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# Skill overrides (clients/<name>/skills/<skill>/SKILL.md)
# ---------------------------------------------------------------------------


def list_client_skill_overrides(client: str) -> list[str]:
    skills_dir = settings.client_dir(client) / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(p.name for p in skills_dir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def _skill_source_dir(skill_name: str, base_domain: str | None = None) -> Path | None:
    """Where to read a *starting point* for a new override from -- the
    current baseline skill, or (for domain-knowledge) a chosen domain's
    current skill. Returns None if there's nothing to start from."""
    if skill_name == "domain-knowledge":
        if not base_domain:
            return None
        return settings.domain_dir(base_domain) / "skills" / "domain-knowledge"
    return settings.default_client_dir() / "skills" / skill_name


def read_skill_starting_point(skill_name: str, base_domain: str | None = None) -> tuple[str, str]:
    """(description, body) to pre-fill the editor with -- from the current
    default/domain skill. Returns ("", "") if there's nothing to start
    from (e.g. domain-knowledge with no base_domain chosen yet)."""
    source = _skill_source_dir(skill_name, base_domain)
    if source is None:
        return "", ""
    skill_md = source / "SKILL.md"
    if not skill_md.is_file():
        return "", ""
    return _parse_skill_file(skill_md)


def _parse_skill_file(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return "", text.strip()
    try:
        front = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        front = {}
    description = str(front.get("description") or "") if isinstance(front, dict) else ""
    return description, match.group(2).strip()


def read_client_skill_override(client: str, skill_name: str) -> tuple[str, str] | None:
    """(description, body) for this client's existing override, or None if
    it doesn't have one yet."""
    path = settings.client_dir(client) / "skills" / skill_name / "SKILL.md"
    if not path.is_file():
        return None
    return _parse_skill_file(path)


def write_skill_override(client: str, skill_name: str, description: str, body: str) -> Path:
    if skill_name not in OVERRIDABLE_SKILLS:
        raise ValidationError(
            f"'{skill_name}' isn't a skill any subagent actually loads -- choose one of: {sorted(OVERRIDABLE_SKILLS)}."
        )
    description = description.strip()
    body = body.strip()
    if not description:
        raise ValidationError(
            "A skill needs a one-sentence description (this is what tells the model when to read it)."
        )
    if not body:
        raise ValidationError("A skill needs some actual instructions in its body.")

    content = f"---\nname: {skill_name}\ndescription: {description}\n---\n\n{body}\n"
    path = settings.client_dir(client) / "skills" / skill_name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def delete_skill_override(client: str, skill_name: str) -> bool:
    import shutil

    skill_dir = settings.client_dir(client) / "skills" / skill_name
    if skill_dir.is_dir():
        shutil.rmtree(skill_dir)
        return True
    return False


# ---------------------------------------------------------------------------
# Custom subagents (clients/<name>/subagents/<name>.md)
# ---------------------------------------------------------------------------


@dataclass
class SubagentDraft:
    name: str
    description: str
    prompt_body: str
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


def validate_subagent_name(name: str) -> str:
    """Kebab-case, ending in "-agent" -- matches the six built-in
    subagents' own naming (discovery-agent, qa-validation-agent, ...) so a
    client-authored one reads identically in logs/task() delegations and
    can never collide with a built-in name."""
    try:
        return settings.validate_kebab_name(name, "subagent name", require_suffix="-agent")
    except ValueError as e:
        raise ValidationError(str(e)) from e


def list_custom_subagents(client: str) -> list[dict]:
    """[{"name", "description"}, ...] for every custom subagent this client
    already has -- enough to render a pick list for editing/deleting."""
    subagents_dir = settings.client_dir(client) / "subagents"
    if not subagents_dir.is_dir():
        return []
    out = []
    for path in sorted(subagents_dir.glob("*.md")):
        draft = _read_subagent_file(path)
        if draft is not None:
            out.append({"name": draft.name, "description": draft.description})
    return out


def _read_subagent_file(path: Path) -> SubagentDraft | None:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    try:
        front = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(front, dict):
        return None
    name = str(front.get("name") or "").strip()
    if not name:
        return None
    tools = front.get("tools") or []
    skills = front.get("skills") or []
    return SubagentDraft(
        name=name,
        description=str(front.get("description") or "").strip(),
        prompt_body=match.group(2).strip(),
        tools=[str(t) for t in tools] if isinstance(tools, list) else [],
        skills=[str(s) for s in skills] if isinstance(skills, list) else [],
    )


def read_custom_subagent(client: str, name: str) -> SubagentDraft | None:
    path = settings.client_dir(client) / "subagents" / f"{name}.md"
    if not path.is_file():
        return None
    return _read_subagent_file(path)


def write_custom_subagent(client: str, draft: SubagentDraft) -> Path:
    validate_subagent_name(draft.name)
    description = draft.description.strip()
    body = draft.prompt_body.strip()
    if not description:
        raise ValidationError(
            "A subagent needs a one-sentence description -- this is what the "
            "orchestrator reads to decide whether/when to delegate to it."
        )
    if not body:
        raise ValidationError("A subagent needs actual instructions (its system prompt).")

    known_tools = available_tools()
    bad_tools = [t for t in draft.tools if t not in known_tools]
    if bad_tools:
        raise ValidationError(f"Unknown tool(s) {bad_tools} -- choose from: {sorted(known_tools)}.")

    known_skills = known_skill_names(client)
    bad_skills = [s for s in draft.skills if s not in known_skills]
    if bad_skills:
        raise ValidationError(f"Unknown skill(s) {bad_skills} -- choose from: {known_skills}.")

    tools_yaml = "[" + ", ".join(draft.tools) + "]"
    skills_yaml = "[" + ", ".join(draft.skills) + "]"
    content = (
        f"---\nname: {draft.name}\ndescription: {description}\n"
        f"tools: {tools_yaml}\nskills: {skills_yaml}\n---\n\n{body}\n"
    )
    path = settings.client_dir(client) / "subagents" / f"{draft.name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def delete_custom_subagent(client: str, name: str) -> bool:
    path = settings.client_dir(client) / "subagents" / f"{name}.md"
    if path.is_file():
        path.unlink()
        return True
    return False
