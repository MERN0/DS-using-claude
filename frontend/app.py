"""
FastAPI app: a dashboard for configuring a client's SYS5 pipeline
customizations, uploading input files, and running a real generation.

This is a stateless REST API -- every request carries whatever client/data
it needs itself, no server-side conversation session -- served alongside
the built React SPA (see `web/`, a separate Vite project; `npm run build`
there produces `web/dist/`, which this app mounts as static files). The
one piece of server-side state is the single in-process generation job
(see `_job` below): this app only ever runs one generation at a time,
checked and enforced in `/api/generate` -- a deliberate simplification
(see `README.md`), not an oversight.

Run with:
    pip install -r requirements.txt
    cd web && npm install && npm run build && cd ..
    python app.py
then open http://localhost:5050/

For frontend development with hot reload, run `npm run dev` in `web/`
instead (its dev server proxies /api/* to this backend -- see
`web/vite.config.js`) and open the Vite dev server's own URL; this
backend's own static mount is only used for the production build.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Optional

_FRONTEND_DIR = Path(__file__).resolve().parent
# This file lives in frontend/ at the repo root, a sibling of backend/ --
# not nested under the SYS5 package -- so the path to sys5_agent/sys5.py
# has to be spelled out rather than assumed to be this file's own parent
# directory.
_REPO_ROOT = _FRONTEND_DIR.parent
_SYS5_DIR = _REPO_ROOT / "backend" / "code" / "artifacts" / "SYS5"
if str(_SYS5_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS5_DIR))

from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import builders as b  # noqa: E402
from sys5 import sys5 as run_sys5  # noqa: E402
from sys5_agent.agent import logsink  # noqa: E402
from sys5_agent.config import settings  # noqa: E402

app = FastAPI(title="SYS5 Test Case Generator")

# Per-upload scratch space, owned entirely by this UI (never read by
# anything else): each upload gets its own input/ dir so two browser tabs
# uploading at the same time can never collide, and each generation writes
# into the matching outputs/<upload_id>/ dir so the download endpoint
# always knows exactly where to look. Not automatically cleaned up --
# see README.md.
_UPLOADS_DIR = _FRONTEND_DIR / "uploads"
_OUTPUTS_DIR = _FRONTEND_DIR / "outputs"
_UPLOADS_DIR.mkdir(exist_ok=True)
_OUTPUTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Config / reference data -- one call the page makes on load to get every
# picklist it needs, all derived from the real settings/tool/skill
# definitions rather than duplicated by hand.
# ---------------------------------------------------------------------------


@app.get("/api/config")
def api_config():
    return {
        "domains": [{"key": d, "label": settings.DOMAIN_LABELS.get(d, d)} for d in settings.DOMAINS],
        "output_formats": settings.SUPPORTED_OUTPUT_FORMATS,
        "clients": b.list_clients(),
        "tools": b.available_tools(),
        "skills": b.OVERRIDABLE_SKILLS,
        "built_in_subagents": b.built_in_subagents(),
        "baseline_memory": b.read_baseline_memory(),
    }


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


class ClientName(BaseModel):
    name: str


@app.post("/api/clients")
def api_create_client(body: ClientName):
    try:
        name = b.validate_client_name(body.name)
    except b.ValidationError as e:
        raise HTTPException(400, str(e)) from e
    # Nothing to write to disk yet -- a client with no customizations still
    # runs fine on baseline rules alone (see builders.py). This just
    # confirms the name is usable; it starts showing up in list_clients()
    # once something is actually saved for it.
    return {"name": name}


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class MemoryBody(BaseModel):
    text: str


@app.get("/api/clients/{client}/memory")
def api_get_memory(client: str):
    return {"text": b.read_client_memory(client)}


@app.put("/api/clients/{client}/memory")
def api_put_memory(client: str, body: MemoryBody):
    try:
        b.write_client_memory(client, body.text)
    except b.ValidationError as e:
        raise HTTPException(400, str(e)) from e
    return {"text": b.read_client_memory(client)}


@app.delete("/api/clients/{client}/memory")
def api_delete_memory(client: str):
    b.delete_client_memory(client)
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Skill overrides
# ---------------------------------------------------------------------------


class SkillBody(BaseModel):
    description: str
    body: str


@app.get("/api/clients/{client}/skills")
def api_list_skills(client: str):
    out = []
    for name in b.list_client_skill_overrides(client):
        existing = b.read_client_skill_override(client, name)
        out.append({"name": name, "description": existing[0] if existing else ""})
    return out


@app.get("/api/skills/{name}/baseline")
def api_skill_baseline(name: str, base_domain: Optional[str] = None):
    """The current baseline skill (same for every client that hasn't
    overridden it) -- read-only reference, independent of any client, so the
    UI can show "what's already active" for a skill even for a client that
    has no override of its own yet."""
    desc, body = b.read_skill_starting_point(name, base_domain)
    return {"description": desc, "body": body}


@app.get("/api/clients/{client}/skills/{name}")
def api_get_skill(client: str, name: str, base_domain: Optional[str] = None):
    """Returns the client's existing override if it has one; otherwise a
    starting point to edit (the current baseline skill, or -- for
    domain-knowledge, which needs `base_domain` -- that domain's current
    skill) so the editor never opens empty."""
    existing = b.read_client_skill_override(client, name)
    if existing:
        return {"description": existing[0], "body": existing[1], "exists": True}
    desc, body = b.read_skill_starting_point(name, base_domain)
    return {"description": desc, "body": body, "exists": False}


@app.put("/api/clients/{client}/skills/{name}")
def api_put_skill(client: str, name: str, payload: SkillBody):
    try:
        b.write_skill_override(client, name, payload.description, payload.body)
    except b.ValidationError as e:
        raise HTTPException(400, str(e)) from e
    return {"saved": True}


@app.delete("/api/clients/{client}/skills/{name}")
def api_delete_skill(client: str, name: str):
    b.delete_skill_override(client, name)
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Custom subagents
# ---------------------------------------------------------------------------


class SubagentBody(BaseModel):
    description: str
    prompt_body: str
    tools: list[str] = []
    skills: list[str] = []


@app.get("/api/clients/{client}/subagents")
def api_list_subagents(client: str):
    return b.list_custom_subagents(client)


@app.get("/api/clients/{client}/subagents/{name}")
def api_get_subagent(client: str, name: str):
    draft = b.read_custom_subagent(client, name)
    if draft is None:
        raise HTTPException(404, "No such subagent.")
    return {
        "description": draft.description,
        "prompt_body": draft.prompt_body,
        "tools": draft.tools,
        "skills": draft.skills,
    }


@app.put("/api/clients/{client}/subagents/{name}")
def api_put_subagent(client: str, name: str, payload: SubagentBody):
    draft = b.SubagentDraft(
        name=name,
        description=payload.description,
        prompt_body=payload.prompt_body,
        tools=payload.tools,
        skills=payload.skills,
    )
    try:
        b.write_custom_subagent(client, draft)
    except b.ValidationError as e:
        raise HTTPException(400, str(e)) from e
    return {"saved": True}


@app.delete("/api/clients/{client}/subagents/{name}")
def api_delete_subagent(client: str, name: str):
    b.delete_custom_subagent(client, name)
    return {"deleted": True}


# ---------------------------------------------------------------------------
# File upload -- the requirements workbook plus whatever supporting
# documents (signal list, command list, etc.) a run needs, all at once.
# ---------------------------------------------------------------------------


@app.post("/api/upload")
async def api_upload(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "No files uploaded.")
    upload_id = uuid.uuid4().hex
    input_dir = _UPLOADS_DIR / upload_id / "input"
    input_dir.mkdir(parents=True)
    saved = []
    for f in files:
        name = Path(f.filename or "").name  # strip any client-supplied path component
        if not name:
            continue
        with (input_dir / name).open("wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(name)
    if not saved:
        shutil.rmtree(input_dir.parent, ignore_errors=True)
        raise HTTPException(400, "No valid files in that upload.")
    return {"upload_id": upload_id, "files": sorted(saved)}


# ---------------------------------------------------------------------------
# Generate -- runs the real pipeline in a background thread (sys5() is a
# long, blocking, synchronous call; running it directly on the request
# would tie up the connection for however long generation takes, easily
# many minutes) and exposes its progress/result through small polling
# endpoints instead.
# ---------------------------------------------------------------------------

_job_lock = threading.Lock()
_job: dict[str, Any] = {"status": "idle", "log": [], "error": None, "result": None}


class GenerateBody(BaseModel):
    client: str
    domain: str
    output_format: str = "xlsx"
    username: str
    current_version: str
    upload_id: str
    requirement_filename: str


def _run_job(params: dict) -> None:
    """Runs on a background thread. Registers a logsink (see
    `sys5_agent/agent/logsink.py`) for the duration so every progress line
    the pipeline already prints to stdout is *also* appended to this job's
    log for the UI to poll -- ops-visible and UI-visible at the same time,
    from the one code path."""

    def sink(line: str) -> None:
        with _job_lock:
            _job["log"].append(line)

    logsink.set_sink(sink)
    try:
        result = run_sys5(**params)
        with _job_lock:
            _job["result"] = result
            if result["success"]:
                _job["status"] = "done"
            else:
                _job["status"] = "error"
                _job["error"] = result.get("final_message") or "Run finished without producing an output file."
    except Exception as e:  # noqa: BLE001 -- reported through job status, must never crash the server thread
        with _job_lock:
            _job["status"] = "error"
            _job["error"] = f"{type(e).__name__}: {e}"
    finally:
        logsink.set_sink(None)


@app.post("/api/generate")
def api_generate(body: GenerateBody):
    with _job_lock:
        if _job["status"] == "running":
            raise HTTPException(409, "A generation is already running -- wait for it to finish first.")

    try:
        client = b.validate_client_name(body.client)
    except b.ValidationError as e:
        raise HTTPException(400, str(e)) from e

    normalized_domain = settings.normalize_domain(body.domain)
    if normalized_domain not in settings.DOMAINS:
        raise HTTPException(400, f"Unknown domain '{body.domain}'.")
    if body.output_format not in settings.SUPPORTED_OUTPUT_FORMATS:
        raise HTTPException(400, f"Unsupported output format '{body.output_format}'.")
    if not body.username.strip() or not body.current_version.strip():
        raise HTTPException(400, "Username and version can't be empty.")

    input_dir = _UPLOADS_DIR / body.upload_id / "input"
    if not input_dir.is_dir():
        raise HTTPException(400, "Unknown upload_id -- upload your files again.")
    if not (input_dir / body.requirement_filename).is_file():
        raise HTTPException(400, f"'{body.requirement_filename}' isn't among the uploaded files.")

    output_dir = _OUTPUTS_DIR / body.upload_id
    output_dir.mkdir(parents=True, exist_ok=True)

    params = dict(
        domain=body.domain,
        output_format=body.output_format,
        project_name=client,
        username=body.username,
        current_version=body.current_version,
        input_folder_path=str(input_dir),
        output_folder_path=str(output_dir),
        requirement_filename=body.requirement_filename,
    )

    with _job_lock:
        _job["status"] = "running"
        _job["log"] = []
        _job["error"] = None
        _job["result"] = None

    threading.Thread(target=_run_job, args=(params,), daemon=True).start()
    return {"started": True}


@app.get("/api/generate/status")
def api_generate_status(since: int = 0):
    """`since`: how many log lines the caller already has, so repeated
    polling only ever sends the new ones instead of the whole log every
    time."""
    with _job_lock:
        return {
            "status": _job["status"],
            "log": _job["log"][since:],
            "log_total": len(_job["log"]),
            "error": _job["error"],
            "download_ready": _job["status"] == "done",
            "summary": (_job["result"] or {}).get("summary") if _job["result"] else None,
        }


@app.get("/api/generate/download")
def api_generate_download():
    with _job_lock:
        result = _job["result"]
        status = _job["status"]
    if status != "done" or not result:
        raise HTTPException(400, "No completed generation to download yet.")
    output_path = Path(result["output_path"])
    if not output_path.is_file():
        raise HTTPException(410, "The output file is no longer on disk.")
    return FileResponse(
        output_path,
        filename=output_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# The built React SPA (see `web/`) -- mounted last, deliberately: Starlette
# matches routes in registration order, so every /api/* path above always
# wins over this catch-all, which only ever serves index.html/JS/CSS/assets.
# ---------------------------------------------------------------------------

_WEB_DIST = _FRONTEND_DIR / "web" / "dist"
if _WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="web")
else:

    @app.get("/")
    def _frontend_not_built():
        raise HTTPException(
            500,
            "The React frontend hasn't been built yet -- run `npm install && npm run build` "
            "in frontend/web/, or `npm run dev` there for local development (see README.md).",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("SYS5_UI_HOST", "127.0.0.1"),
        port=int(os.environ.get("SYS5_UI_PORT", "5050")),
    )
