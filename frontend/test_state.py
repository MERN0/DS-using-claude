"""
End-to-end regression test for the chat state machine, run against a
scratch `clients/` directory so it never touches real client data.

Run with:
    python test_state.py
(plain script, not pytest -- no test framework dependency for a UI this
small; each `assert` failure points at the exact step that broke).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_SCRATCH = Path("/tmp/sys5_frontend_test_state")


def _fresh_clients_dir() -> Path:
    import builders as b

    shutil.rmtree(_SCRATCH, ignore_errors=True)
    _SCRATCH.mkdir(parents=True)
    b.settings.CLIENTS_DIR = _SCRATCH
    return _SCRATCH


def test_full_flow() -> None:
    import state as s

    tmp = _fresh_clients_dir()
    session = s.start_session()

    # -- welcome / create client --
    turn = s.process(session, {})
    assert session["step"] == "welcome"
    turn = s.process(session, {"text": "acme"})
    assert session["client"] == "acme"
    assert session["step"] == "main_menu"

    # -- memory rule --
    s.process(session, {"value": "add_memory"})
    assert session["step"] == "memory_edit"
    s.process(session, {"text": "Always use imperial units for this client."})
    assert session["step"] == "memory_preview"
    s.process(session, {"value": "save"})
    assert session["step"] == "main_menu"
    assert "imperial units" in (tmp / "acme" / "memory" / "AGENTS.md").read_text()

    # -- skill override --
    s.process(session, {"value": "add_skill"})
    s.process(session, {"value": "writing-style"})
    assert session["step"] == "skill_description"
    s.process(session, {"text": "Acme's own writing style."})
    assert session["step"] == "skill_body"
    s.process(session, {"text": "Use imperial units only, never metric."})
    assert session["step"] == "skill_preview"
    s.process(session, {"value": "save"})
    assert session["step"] == "main_menu"
    assert (tmp / "acme" / "skills" / "writing-style" / "SKILL.md").is_file()

    # -- custom subagent --
    s.process(session, {"value": "add_subagent"})
    assert session["step"] == "subagent_name"
    s.process(session, {"text": "extra-safety-checks-agent"})
    assert session["step"] == "subagent_description"
    s.process(session, {"text": "Cross-checks ISO 26262 tagging."})
    assert session["step"] == "subagent_prompt"
    s.process(session, {"text": "Check every resolved signal against the ASIL column."})
    assert session["step"] == "subagent_tools"
    s.process(session, {"selected": ["search_sheet", "read_sheet_range", "bogus_tool"]})
    assert session["step"] == "subagent_skills"
    s.process(session, {"selected": ["domain-knowledge", "writing-style"]})
    assert session["step"] == "subagent_preview"
    s.process(session, {"value": "save"})
    assert session["step"] == "main_menu"
    subagent_path = tmp / "acme" / "subagents" / "extra-safety-checks-agent.md"
    assert subagent_path.is_file()
    content = subagent_path.read_text()
    assert "search_sheet" in content and "bogus_tool" not in content

    # -- manage: edit the subagent in place --
    s.process(session, {"value": "manage"})
    s.process(session, {"value": "subagents"})
    assert session["step"] == "manage_subagents_list"
    s.process(session, {"value": "extra-safety-checks-agent"})
    assert session["step"] == "manage_subagent_detail"
    s.process(session, {"value": "edit"})
    assert session["step"] == "subagent_description"
    s.process(session, {"text": "UPDATED description."})
    s.process(session, {"text": "UPDATED prompt body."})
    s.process(session, {"selected": ["search_sheet"]})
    s.process(session, {"selected": []})
    assert session["step"] == "subagent_preview"
    s.process(session, {"value": "save"})
    content = subagent_path.read_text()
    assert "UPDATED description." in content and "UPDATED prompt body." in content

    # -- manage: delete the skill override --
    s.process(session, {"value": "manage"})
    s.process(session, {"value": "skills"})
    s.process(session, {"value": "writing-style"})
    assert session["step"] == "manage_skill_detail"
    s.process(session, {"value": "delete"})
    s.process(session, {"value": "yes"})
    assert not (tmp / "acme" / "skills" / "writing-style").exists()

    # -- finish and restart --
    s.process(session, {"value": "done"})
    assert session["step"] == "end"
    s.process(session, {"value": "restart"})
    assert session["step"] == "welcome"
    assert session["client"] is None

    shutil.rmtree(tmp, ignore_errors=True)
    print("test_full_flow: OK")


def test_validation_errors_dont_advance() -> None:
    import state as s

    tmp = _fresh_clients_dir()
    session = s.start_session()
    s.process(session, {})

    # An unsafe client name must not advance past "welcome".
    s.process(session, {"text": "../etc"})
    assert session["step"] == "welcome"
    assert session["client"] is None

    s.process(session, {"text": "acme"})
    assert session["step"] == "main_menu"

    # An unsafe subagent name must not advance past "subagent_name".
    s.process(session, {"value": "add_subagent"})
    s.process(session, {"text": "not a valid name!"})
    assert session["step"] == "subagent_name"

    shutil.rmtree(tmp, ignore_errors=True)
    print("test_validation_errors_dont_advance: OK")


if __name__ == "__main__":
    test_full_flow()
    test_validation_errors_dont_advance()
    print("ALL OK")
