"""
Constructs the deep agent for one run: model, run workspace, layered
client memory/skills, subagents, and the top-level write tool.

Client memory (AGENTS.md) and skills (SKILL.md dirs) are resolved and
copied into a fresh per-run workspace before the agent is built, rather
than referenced in place, so that:
  - the deepagents `memory`/`skills` params (which are paths relative to
    the FilesystemBackend root) can point at one simple root, and
  - each run is a self-contained, reproducible snapshot of the rules that
    were actually in effect, even if the client's `clients/<name>/`
    directory is edited later.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_openai import ChatOpenAI

from sys5_agent.agent.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from sys5_agent.agent.subagents import ALL_SUBAGENTS
from sys5_agent.config import settings
from sys5_agent.tools.excel_tools import write_output_workbook


def _new_run_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = settings.RUNS_DIR / stamp
    (run_dir / "memory").mkdir(parents=True, exist_ok=True)
    (run_dir / "skills").mkdir(parents=True, exist_ok=True)
    (run_dir / "resolved").mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_layered_memory(run_dir: Path, client: str) -> None:
    default_agents_md = settings.default_client_dir() / "memory" / "AGENTS.md"
    client_agents_md = settings.client_dir(client) / "memory" / "AGENTS.md"

    parts = []
    if default_agents_md.is_file():
        parts.append(default_agents_md.read_text(encoding="utf-8"))
    if client != settings.DEFAULT_CLIENT_DIR_NAME and client_agents_md.is_file():
        parts.append(f"\n---\n\n# Client-specific rules: {client}\n\n" + client_agents_md.read_text(encoding="utf-8"))

    (run_dir / "memory" / "AGENTS.md").write_text("\n".join(parts), encoding="utf-8")


def _copy_layered_skills(run_dir: Path, client: str) -> None:
    dest = run_dir / "skills"

    default_skills = settings.default_client_dir() / "skills"
    if default_skills.is_dir():
        for skill_dir in default_skills.iterdir():
            if skill_dir.is_dir():
                shutil.copytree(skill_dir, dest / skill_dir.name, dirs_exist_ok=True)

    if client != settings.DEFAULT_CLIENT_DIR_NAME:
        client_skills = settings.client_dir(client) / "skills"
        if client_skills.is_dir():
            for skill_dir in client_skills.iterdir():
                if skill_dir.is_dir():
                    # Client skill of the same name fully overrides the default one.
                    override_dest = dest / skill_dir.name
                    if override_dest.exists():
                        shutil.rmtree(override_dest)
                    shutil.copytree(skill_dir, override_dest)


def build_agent(client: str):
    """Build a fresh deep agent + its run workspace directory for one run.

    Returns (agent, run_dir).
    """
    run_dir = _new_run_dir()
    _write_layered_memory(run_dir, client)
    _copy_layered_skills(run_dir, client)

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
        tools=[write_output_workbook],
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        backend=backend,
        memory=["memory/AGENTS.md"],
        skills=["skills/"],
        subagents=ALL_SUBAGENTS,
        debug=settings.DEBUG,
    )

    return agent, run_dir
