# SYS5 Test Case Generator — dashboard UI

A small, self-contained FastAPI app for configuring a client's
customizations to the SYS2→SYS5 pipeline, uploading a requirements
workbook (plus supporting documents), and running a real generation —
ending with a downloadable SYS5 test-case workbook.

This directory (`frontend/`) lives at the repo root, alongside `backend/`
— the pipeline it configures and runs is under
[`backend/code/artifacts/SYS5/`](../backend/code/artifacts/SYS5/). See the
main [architecture guide](../backend/code/artifacts/SYS5/README.md) first
if you haven't — this UI is a form-based front end for concepts explained
there (clients, skills, memory, subagents, the pipeline itself).

## What it does

**Configure a client** — three kinds of customization, each validated
against exactly what the pipeline expects (unknown tool/skill name,
missing required field, unsafe name — all rejected with an explanation
before anything is written):

- **Memory rules** (`clients/<name>/memory/AGENTS.md`) — a standing
  instruction always in effect for that client.
- **Skill overrides** (`clients/<name>/skills/<skill>/SKILL.md`) — replace
  one of the four baseline skills (or the domain-knowledge skill) with the
  client's own version.
- **Custom subagents** (`clients/<name>/subagents/<name>.md`) — an
  additional specialist the orchestrator can delegate to for that client,
  alongside the fixed six the pipeline always runs. Never a replacement
  for the six-phase pipeline, only an addition to it.

**Run a real generation** — upload the SYS2 requirements workbook plus any
supporting documents, pick the domain/output format/version, and click
Generate. The pipeline runs in the background (a real generation can take
many minutes); the page polls for live progress — the exact same lines the
CLI prints to its own terminal, see `sys5_agent/agent/logsink.py` — and
shows a download link once the output workbook is ready.

## How generation actually runs

`POST /api/generate` starts `sys5()` (the same function the CLI and any
real backend integration call — see the main README's
[How to run it](../backend/code/artifacts/SYS5/README.md#how-to-run-it))
on a background thread, since it's a long, blocking, synchronous call that
would otherwise tie up the HTTP connection for the run's entire duration.
`GET /api/generate/status` polls the job's state and log; `GET
/api/generate/download` streams the resulting workbook once it's done.

**This app runs at most one generation at a time, process-wide** — a
second `/api/generate` call while one is already running gets rejected
(409) rather than queued. This is a deliberate simplification, not an
oversight: supporting several truly concurrent runs safely (isolated
progress logs, isolated job state per run) is real additional complexity
this tool doesn't need to take on to be useful. If you need to run several
generations back to back, just wait for each one to finish before
starting the next.

Uploaded input files and generated output workbooks live under
`frontend/uploads/<upload-id>/` and `frontend/outputs/<upload-id>/`
respectively — scratch space owned entirely by this UI, not read by
anything else, and not automatically cleaned up (delete them periodically
if disk space matters to you; `.gitignore` already excludes both from
version control).

## Running it

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5050/`. Set `SYS5_UI_PORT`/`SYS5_UI_HOST` to
change where it listens. For production-style serving, run it with
`uvicorn app:app` directly instead (e.g. behind a reverse proxy) rather
than the `python app.py` dev-server entry point.

A real generation needs the pipeline's own LLM endpoint configured first —
see the main README's [How to run it](../backend/code/artifacts/SYS5/README.md#how-to-run-it)
for the `SYS5_LLM_*` environment variables. Configuring a client (memory/
skills/subagents) works fine without one; only clicking Generate needs it.

## How it's built

- `app.py` — the FastAPI routes: reference data (`/api/config`), CRUD for
  a client's memory/skills/subagents (thin wrappers around `builders.py`),
  file upload, and the generate/status/download job endpoints. Stateless
  per request except the one global job dict.
- `builders.py` — the only module that actually reads/writes files under
  `clients/<name>/`. Adds the SYS5 package to `sys.path` itself (it lives
  outside `backend/`, so this isn't automatic) and then reuses the
  pipeline's own validation directly — `sys5_agent.config.settings.
  validate_safe_name`, the real tool list from `sys5_agent.tools.
  excel_tools` — rather than duplicating any of it. No FastAPI dependency,
  so it's testable on its own.
- `templates/index.html` + `static/app.js` + `static/style.css` —
  Bootstrap 5 (via CDN) for styling; vanilla JS handling the four panels
  (memory / skills / subagents / generate) and polling job status during
  a run.
- `test_app.py` — end-to-end regression test against a scratch `clients/`
  directory and a mocked `sys5()` (no real LLM needed) covering the CRUD
  endpoints, the upload → generate → poll → download lifecycle, and the
  single-job-at-a-time guard. Run with `python test_app.py`.
