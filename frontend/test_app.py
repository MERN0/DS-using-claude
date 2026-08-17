"""
End-to-end regression test for the FastAPI dashboard, run against a scratch
`clients/` directory and a *mocked* `sys5()` (no real LLM available here --
this verifies the whole job lifecycle -- upload, background thread, status
polling, download, the single-job-at-a-time guard -- independent of what
the pipeline itself actually does).

Run with:
    python test_app.py
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

_SCRATCH_CLIENTS = Path("/tmp/sys5_frontend_test_app_clients")
_SCRATCH_UI = Path("/tmp/sys5_frontend_test_app_ui")

# Captured once, before any test mutates settings.CLIENTS_DIR (a module-level
# global -- once one test overwrites it, settings.default_client_dir() would
# otherwise recompute against the *scratch* dir on every later call).
import builders as _b_for_capture  # noqa: E402

_REAL_DEFAULT_CLIENT_DIR = _b_for_capture.settings.default_client_dir()


def _fresh_env():
    import app as app_mod
    import builders as b

    shutil.rmtree(_SCRATCH_CLIENTS, ignore_errors=True)
    shutil.rmtree(_SCRATCH_UI, ignore_errors=True)
    _SCRATCH_CLIENTS.mkdir(parents=True)
    _SCRATCH_UI.mkdir(parents=True)
    # Swapping CLIENTS_DIR wholesale for test isolation also hides the real
    # _default/ baseline skills that ship with the repo (settings.CLIENTS_DIR
    # is never actually swapped in production, so _default is always there)
    # -- carry it over so read_skill_starting_point() has something real to
    # read, same as it would against the live clients/ directory.
    shutil.copytree(_REAL_DEFAULT_CLIENT_DIR, _SCRATCH_CLIENTS / _REAL_DEFAULT_CLIENT_DIR.name)
    b.settings.CLIENTS_DIR = _SCRATCH_CLIENTS
    app_mod._UPLOADS_DIR = _SCRATCH_UI / "uploads"
    app_mod._OUTPUTS_DIR = _SCRATCH_UI / "outputs"
    app_mod._UPLOADS_DIR.mkdir()
    app_mod._OUTPUTS_DIR.mkdir()
    # `app` is a real module, imported once and reused across every test
    # function in this process -- without resetting these, a later test
    # would see a previous test's completed job/run state instead of a
    # clean slate, regardless of run order.
    app_mod._job = {"status": "idle", "log": [], "error": None, "result": None}
    app_mod._run_state = None
    return app_mod, b


def test_config_and_client_crud() -> None:
    from starlette.testclient import TestClient

    app_mod, b = _fresh_env()
    client = TestClient(app_mod.app)

    # "/" serves the built React SPA (see web/dist/) if it's been built, or a
    # helpful 500 pointing at `npm run build` otherwise -- either is fine
    # here, this suite doesn't require Node/npm to run.
    r = client.get("/")
    if (Path(__file__).resolve().parent / "web" / "dist").is_dir():
        assert r.status_code == 200 and "SYS5 Test Case Generator" in r.text
    else:
        assert r.status_code == 500 and "npm run build" in r.text

    r = client.get("/api/config")
    data = r.json()
    assert "bcm" in [d["key"] for d in data["domains"]]
    assert "writing-style" in data["skills"]
    assert "search_sheet" in data["tools"]
    assert "baseline rules" in data["baseline_memory"].lower()
    assert len(data["built_in_subagents"]) == 6
    assert data["built_in_subagents"][0]["name"] == "discovery-agent"
    assert isinstance(data["llm_context_tokens"], int) and data["llm_context_tokens"] > 0

    r = client.get("/api/skills/writing-style/baseline")
    baseline = r.json()
    assert baseline["body"]  # the real baseline skill body, not empty

    r = client.get("/api/skills/domain-knowledge/baseline")
    assert r.json()["body"] == ""  # no base_domain given -- nothing to show yet
    r = client.get("/api/skills/domain-knowledge/baseline?base_domain=bcm")
    assert r.json()["body"]

    r = client.post("/api/clients", json={"name": "acme"})
    assert r.status_code == 200 and r.json()["name"] == "acme"

    r = client.post("/api/clients", json={"name": "../etc"})
    assert r.status_code == 400

    # New-client naming convention (settings.validate_kebab_name): lowercase
    # kebab-case only, sane length. validate_client_name (used to reference
    # a possibly pre-existing client, e.g. before generating) stays lenient
    # -- only the create-a-new-project path enforces this.
    for bad_name in ["Acme_Corp", "a", "a" * 65, "-acme", "acme-"]:
        r = client.post("/api/clients", json={"name": bad_name})
        assert r.status_code == 400, bad_name
    r = client.post("/api/clients", json={"name": "acme-corp-2"})
    assert r.status_code == 200 and r.json()["name"] == "acme-corp-2"

    print("test_config_and_client_crud: OK")


def test_memory_skill_subagent_crud() -> None:
    from starlette.testclient import TestClient

    app_mod, b = _fresh_env()
    client = TestClient(app_mod.app)

    # Memory
    r = client.get("/api/clients/acme/memory")
    assert r.json()["text"] == ""
    r = client.put("/api/clients/acme/memory", json={"text": "Always use imperial units."})
    assert r.status_code == 200
    r = client.get("/api/clients/acme/memory")
    assert "imperial units" in r.json()["text"]
    r = client.delete("/api/clients/acme/memory")
    assert r.json()["deleted"] is True

    # Skills
    r = client.get("/api/clients/acme/skills")
    assert r.json() == []
    r = client.get("/api/clients/acme/skills/writing-style")
    starting_point = r.json()
    assert starting_point["exists"] is False
    assert starting_point["body"]  # pre-filled from the default skill

    r = client.put(
        "/api/clients/acme/skills/writing-style",
        json={"description": "Acme style.", "body": "Imperial units only."},
    )
    assert r.status_code == 200
    r = client.get("/api/clients/acme/skills")
    assert r.json() == [{"name": "writing-style", "description": "Acme style."}]

    r = client.put("/api/clients/acme/skills/not-a-real-skill", json={"description": "x", "body": "y"})
    assert r.status_code == 400

    r = client.delete("/api/clients/acme/skills/writing-style")
    assert r.json()["deleted"] is True

    # Subagents
    r = client.get("/api/clients/acme/subagents")
    assert r.json() == []

    # Naming convention (settings.validate_kebab_name, require_suffix="-agent"):
    # matches the six built-in subagents' own naming so a custom one reads
    # identically in logs/task() delegations and can never collide with one.
    for bad_name in ["extra-checks", "Extra-Checks-Agent", "extra_checks_agent"]:
        r = client.put(
            f"/api/clients/acme/subagents/{bad_name}",
            json={"description": "x", "prompt_body": "y", "tools": [], "skills": []},
        )
        assert r.status_code == 400, bad_name

    r = client.put(
        "/api/clients/acme/subagents/extra-checks-agent",
        json={
            "description": "Cross-checks ISO 26262 tagging.",
            "prompt_body": "Check the ASIL column.",
            "tools": ["search_sheet", "bogus_tool"],
            "skills": ["domain-knowledge"],
        },
    )
    assert r.status_code == 400  # bogus_tool rejected

    r = client.put(
        "/api/clients/acme/subagents/extra-checks-agent",
        json={
            "description": "Cross-checks ISO 26262 tagging.",
            "prompt_body": "Check the ASIL column.",
            "tools": ["search_sheet"],
            "skills": ["domain-knowledge"],
        },
    )
    assert r.status_code == 200
    r = client.get("/api/clients/acme/subagents/extra-checks-agent")
    assert r.json()["tools"] == ["search_sheet"]
    r = client.get("/api/clients/acme/subagents")
    assert len(r.json()) == 1
    r = client.delete("/api/clients/acme/subagents/extra-checks-agent")
    assert r.json()["deleted"] is True
    r = client.get("/api/clients/acme/subagents/extra-checks-agent")
    assert r.status_code == 404

    print("test_memory_skill_subagent_crud: OK")


def test_upload_and_generate_lifecycle() -> None:
    from starlette.testclient import TestClient

    app_mod, b = _fresh_env()
    client = TestClient(app_mod.app)

    files = [
        ("files", ("SYS2_Requirements.xlsx", io.BytesIO(b"fake xlsx bytes"), "application/octet-stream")),
        ("files", ("Signals.xlsx", io.BytesIO(b"fake xlsx bytes"), "application/octet-stream")),
    ]
    r = client.post("/api/upload", files=files)
    assert r.status_code == 200
    upload = r.json()
    assert sorted(upload["files"]) == ["SYS2_Requirements.xlsx", "Signals.xlsx"]
    upload_id = upload["upload_id"]

    # Fake a completed run: write an output file plus a fake run workspace
    # (clusters.jsonl, requirements_index.jsonl, draft_testcases.jsonl, a
    # resolved/*.md, qa_report.md -- one malformed line included, on
    # purpose) and emit the same run_events a real run would, so the new
    # /api/generate/status fields and /api/generate/workspace/* endpoints
    # have something real to serve.
    def fake_sys5(**kwargs):
        from sys5_agent.agent import logsink, run_events

        run_dir = Path(kwargs["output_folder_path"]) / "fake_run_workspace"
        (run_dir / "resolved").mkdir(parents=True)
        run_events.emit({"type": "run_dir", "run_dir": str(run_dir)})

        logsink.emit("[fake] discovery phase...")
        run_events.emit({"type": "phase_start", "subagent": "discovery-agent", "description": "classify sheets"})
        run_events.emit({"type": "todos", "todos": [{"content": "discovery", "status": "in_progress"}]})
        run_events.emit({"type": "skill_read", "skill": "writing-style"})
        run_events.emit({"type": "phase_end", "subagent": "discovery-agent", "elapsed": 0.05})

        (run_dir / "clusters.jsonl").write_text(
            json.dumps({"cluster_id": "c1", "check_type": "Boundary Value Check", "requirement_ids": ["REQ-1"]})
            + "\nnot valid json\n"
        )
        (run_dir / "requirements_index.jsonl").write_text(json.dumps({"id": "REQ-1", "text": "door lock req"}) + "\n")
        (run_dir / "draft_testcases.jsonl").write_text(
            json.dumps({"Test Case ID": "TC_1", "Traceability": "REQ-1"}) + "\n"
        )
        (run_dir / "resolved" / "c1.md").write_text("DoorLockCmd -> alias DLC")
        (run_dir / "qa_report.md").write_text("All checks passed.")

        time.sleep(0.3)  # gives the concurrent-request assertion below a real window to observe "running" in
        logsink.emit("[fake] writing output...")
        output_dir = Path(kwargs["output_folder_path"])
        output_path = output_dir / f"{kwargs['project_name']}_SYS5_{kwargs['current_version']}.xlsx"
        output_path.write_bytes(b"fake generated workbook")
        return {
            "success": True,
            "output_path": str(output_path),
            "run_dir": str(run_dir),
            "summary": {"requirements_found": 3},
            "final_message": "Done.",
        }

    with patch.object(app_mod, "run_sys5", side_effect=fake_sys5):
        r = client.post(
            "/api/generate",
            json={
                "client": "acme",
                "domain": "bcm",
                "output_format": "xlsx",
                "username": "tester",
                "current_version": "v1",
                "upload_id": upload_id,
                "requirement_filename": "SYS2_Requirements.xlsx",
            },
        )
        assert r.status_code == 200, r.text

        # A second concurrent generate must be rejected.
        r2 = client.post(
            "/api/generate",
            json={
                "client": "acme",
                "domain": "bcm",
                "output_format": "xlsx",
                "username": "tester",
                "current_version": "v1",
                "upload_id": upload_id,
                "requirement_filename": "SYS2_Requirements.xlsx",
            },
        )
        assert r2.status_code == 409

        deadline = time.time() + 5
        status = None
        while time.time() < deadline:
            status = client.get("/api/generate/status").json()
            if status["status"] != "running":
                break
            time.sleep(0.05)
        assert status is not None and status["status"] == "done", status
        assert status["download_ready"] is True
        assert status["summary"] == {"requirements_found": 3}
        assert any("fake" in line for line in status["log"]) or status["log_total"] > 0

        # New structured status fields (run_events -> RunStateAggregator).
        assert status["run_dir"] and status["run_dir"].endswith("fake_run_workspace")
        assert status["todos"] == [{"content": "discovery", "status": "in_progress"}]
        assert status["subagent_usage"]["discovery-agent"]["calls"] == 1
        assert status["subagent_usage"]["discovery-agent"]["total_seconds"] == 0.05
        assert status["skill_usage"]["writing-style"]["reads"] == 1
        assert status["current_phase"] is None  # phase_end already fired

        r = client.get("/api/generate/download")
        assert r.status_code == 200
        assert r.content == b"fake generated workbook"

        # Workspace data endpoints, against the fake workspace fake_sys5 wrote.
        r = client.get("/api/generate/workspace")
        manifest = r.json()
        assert manifest["clusters"] is True
        assert manifest["resolved_cluster_ids"] == ["c1"]

        r = client.get("/api/generate/workspace/clusters")
        clusters = r.json()
        assert clusters[0] == {
            "cluster_id": "c1",
            "check_type": "Boundary Value Check",
            "requirement_ids": ["REQ-1"],
            "requirement_count": 1,
        }
        assert clusters[1]["_parse_error"]  # the deliberately-malformed line, not a 500

        r = client.get("/api/generate/workspace/requirements?cluster_id=c1")
        assert r.json() == [{"id": "REQ-1", "text": "door lock req"}]

        r = client.get("/api/generate/workspace/testcases")
        testcases = r.json()
        assert testcases[0]["_cluster_id"] == "c1"
        assert testcases[0]["_check_type"] == "Boundary Value Check"

        r = client.get("/api/generate/workspace/resolved/c1")
        assert r.json() == {"cluster_id": "c1", "markdown": "DoorLockCmd -> alias DLC"}
        r = client.get("/api/generate/workspace/resolved/does-not-exist")
        assert r.status_code == 404

        r = client.get("/api/generate/workspace/qa_report")
        assert r.json() == {"markdown": "All checks passed."}

        # run_summary.json was never written to the fake workspace (only
        # returned in the mocked result dict) -- the endpoint reads the real
        # file, so this is the correct "not there" case, not a bug.
        r = client.get("/api/generate/workspace/summary")
        assert r.status_code == 404

    print("test_upload_and_generate_lifecycle: OK")


def test_workspace_endpoints_404_before_any_run() -> None:
    from starlette.testclient import TestClient

    app_mod, b = _fresh_env()
    client = TestClient(app_mod.app)

    for path in (
        "/api/generate/workspace",
        "/api/generate/workspace/clusters",
        "/api/generate/workspace/testcases",
        "/api/generate/workspace/resolved/c1",
        "/api/generate/workspace/qa_report",
        "/api/generate/workspace/summary",
    ):
        r = client.get(path)
        assert r.status_code == 404, (path, r.text)

    status = client.get("/api/generate/status").json()
    assert status["todos"] == []
    assert status["current_phase"] is None
    assert status["subagent_usage"] == {}
    assert status["run_dir"] is None

    print("test_workspace_endpoints_404_before_any_run: OK")


def test_generate_rejects_bad_input() -> None:
    from starlette.testclient import TestClient

    app_mod, b = _fresh_env()
    client = TestClient(app_mod.app)

    r = client.post(
        "/api/generate",
        json={
            "client": "acme",
            "domain": "not-a-real-domain",
            "output_format": "xlsx",
            "username": "tester",
            "current_version": "v1",
            "upload_id": "does-not-exist",
            "requirement_filename": "whatever.xlsx",
        },
    )
    assert r.status_code == 400

    print("test_generate_rejects_bad_input: OK")


if __name__ == "__main__":
    test_config_and_client_crud()
    test_memory_skill_subagent_crud()
    test_upload_and_generate_lifecycle()
    test_generate_rejects_bad_input()
    test_workspace_endpoints_404_before_any_run()
    shutil.rmtree(_SCRATCH_CLIENTS, ignore_errors=True)
    shutil.rmtree(_SCRATCH_UI, ignore_errors=True)
    print("ALL OK")
