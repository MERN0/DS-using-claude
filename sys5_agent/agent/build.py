"""
Constructs the deep agent for one run: model, run workspace, layered
client/domain memory & skills, subagents, and the top-level write tool.

Client memory (AGENTS.md) and skills (SKILL.md dirs) are resolved and
copied into a fresh per-run workspace before the agent is built, rather
than referenced in place, so that:
  - the deepagents `memory`/`skills` params (which are paths relative to
    the FilesystemBackend root) can point at one simple root, and
  - each run is a self-contained, reproducible snapshot of the rules that
    were actually in effect, even if the client's `clients/<name>/`
    directory is edited later.

Skills layer in three tiers, each able to override a same-named skill from
the previous one: baseline (`clients/_default/skills/`) -> domain
(`domains/<domain>/skills/`, e.g. the `domain-knowledge` skill) -> client
(`clients/<name>/skills/`). The domain is fixed for the whole run (passed
once via `--domain`), unlike per-cluster/per-chunk work.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_openai import ChatOpenAI

from sys5_agent.agent.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from sys5_agent.agent.subagents import build_subagents
from sys5_agent.config import settings
from sys5_agent.tools.excel_tools import build_write_tool


def _new_run_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = settings.RUNS_DIR / stamp
    (run_dir / "memory").mkdir(parents=True, exist_ok=True)
    (run_dir / "skills").mkdir(parents=True, exist_ok=True)
    (run_dir / "resolved").mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_layered_memory(run_dir: Path, client: str, domain: str) -> None:
    default_agents_md = settings.default_client_dir() / "memory" / "AGENTS.md"
    client_agents_md = settings.client_dir(client) / "memory" / "AGENTS.md"

    parts = []
    if default_agents_md.is_file():
        parts.append(default_agents_md.read_text(encoding="utf-8"))

    domain_label = settings.DOMAIN_LABELS.get(domain, domain)
    parts.append(
        f"\n---\n\n# Domain for this run: {domain} ({domain_label})\n\n"
        "This run's automotive domain is fixed for the whole cycle -- it "
        "will not change mid-run. The `domain-knowledge` skill (loaded "
        "alongside the standard skills) carries this domain's detailed "
        "items: typical ECUs/modules, signal and command naming "
        "conventions, relevant vehicle networks, common requirement/test "
        "patterns, and terminology pitfalls. Read it early (e.g. during "
        "discovery) and revisit it whenever requirement text or a "
        "supporting document uses domain terminology that isn't "
        "immediately clear."
    )

    if client != settings.DEFAULT_CLIENT_DIR_NAME and client_agents_md.is_file():
        parts.append(f"\n---\n\n# Client-specific rules: {client}\n\n" + client_agents_md.read_text(encoding="utf-8"))

    (run_dir / "memory" / "AGENTS.md").write_text("\n".join(parts), encoding="utf-8")


def _copy_skill_overrides(dest: Path, skills_dir: Path) -> None:
    """Copy every skill dir under skills_dir into dest, overriding any
    same-named skill already copied there (last layer wins)."""
    if not skills_dir.is_dir():
        return
    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir():
            override_dest = dest / skill_dir.name
            if override_dest.exists():
                shutil.rmtree(override_dest)
            shutil.copytree(skill_dir, override_dest)


def _copy_layered_skills(run_dir: Path, client: str, domain: str) -> None:
    dest = run_dir / "skills"

    default_skills = settings.default_client_dir() / "skills"
    if default_skills.is_dir():
        for skill_dir in default_skills.iterdir():
            if skill_dir.is_dir():
                shutil.copytree(skill_dir, dest / skill_dir.name, dirs_exist_ok=True)

    # Domain skills (e.g. domain-knowledge) layer on top of the defaults,
    # then client skills layer on top of the domain -- a client override of
    # domain-knowledge, if one is ever added, wins last.
    _copy_skill_overrides(dest, settings.domain_dir(domain) / "skills")

    if client != settings.DEFAULT_CLIENT_DIR_NAME:
        _copy_skill_overrides(dest, settings.client_dir(client) / "skills")


def build_agent(client: str, domain: str, input_dir: Path, output_path: Path):
    """Build a fresh deep agent + its run workspace directory for one run.

    `domain` is the automotive domain for this run (e.g. "bcm", "adas") --
    it stays constant for the whole cycle and determines which
    domain-knowledge skill gets loaded.

    `input_dir` and `output_path` bound this run's real filesystem access:
    every excel tool the orchestrator and its subagents get is built by a
    factory closed over these two paths (see `tools/excel_tools.py`), so the
    agent can read only inside `input_dir` and can only ever write to
    `output_path` -- never anywhere else on disk. This is on top of (not a
    replacement for) the run workspace's own `virtual_mode` sandbox below.

    Returns (agent, run_dir).
    """
    domain = settings.normalize_domain(domain)
    input_dir = Path(input_dir).resolve()
    if not input_dir.is_dir():
        raise ValueError(f"input_dir does not exist or is not a directory: {input_dir}")
    output_path = Path(output_path).resolve()

    run_dir = _new_run_dir()
    _write_layered_memory(run_dir, client, domain)
    _copy_layered_skills(run_dir, client, domain)

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        openai_api_key=settings.LLM_API_KEY,
        openai_api_base=settings.LLM_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
    )

    # virtual_mode=True sandboxes the agent's built-in filesystem tools
    # (ls/read_file/write_file/edit_file) to root_dir -- without it, '..' or
    # an absolute path can escape the run workspace, which would break the
    # filesystem-separation guarantee this design relies on.
    backend = FilesystemBackend(root_dir=str(run_dir), virtual_mode=True)

    agent = create_deep_agent(
        model=llm,
        tools=[build_write_tool(output_path)],
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        backend=backend,
        memory=["memory/AGENTS.md"],
        skills=["skills/"],
        subagents=build_subagents(input_dir),
        debug=settings.DEBUG,
    )

    return agent, run_dir
