# SYS5 Test Case Generator — dashboard UI

A React dashboard (`web/`) backed by a small, self-contained FastAPI app
(`app.py`) for configuring a client's customizations to the SYS2→SYS5
pipeline, uploading a requirements workbook (plus supporting documents),
and running a real generation — ending with a downloadable SYS5 test-case
workbook.

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
before anything is written). Every panel shows two layers: what's already
active for every client (read-only reference) and what this client adds on
top (editable) — a fresh client's editable box being empty doesn't mean
"nothing is configured", and the read-only layer makes that visible instead
of leaving the user to guess:

- **Memory rules** (`clients/<name>/memory/AGENTS.md`) — the Memory tab
  shows the baseline rules every run already loads (collapsible, read-only)
  above the client's own standing instruction, which is *appended* to the
  baseline at run time, never a replacement for it (see `agent/build.py`'s
  `_write_layered_memory`).
- **Skill overrides** (`clients/<name>/skills/<skill>/SKILL.md`) — the
  Skills tab lists all five overridable skills with a "Baseline" or "Custom
  override" badge and a "View baseline" button per skill, so the current
  baseline body is always one click away, then a form to add/replace this
  client's own version.
- **Custom subagents** (`clients/<name>/subagents/<name>.md`) — the
  Subagents tab lists the fixed six subagents the pipeline always runs
  first (read-only reference, from `agent/subagents.py`), then this
  client's additional specialists. Custom subagents are never a
  replacement for the six-phase pipeline, only an addition to it.

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

One-time setup, then the usual dev loop:

```bash
pip install -r requirements.txt
cd web && npm install && cd ..
```

**Day-to-day development** (hot reload for the UI): run the backend and
the Vite dev server side by side, in two terminals.

```bash
python app.py                 # terminal 1 -- backend on :5050
cd web && npm run dev          # terminal 2 -- UI on :5173, proxies /api/* to :5050
```

Open `http://localhost:5173/`.

**Single-command / production-style run**: build the React app once, then
the FastAPI backend alone serves everything (UI + API) on one port.

```bash
cd web && npm run build && cd ..
python app.py
```

Open `http://localhost:5050/`. Set `SYS5_UI_PORT`/`SYS5_UI_HOST` to change
where it listens; run `uvicorn app:app` directly instead of `python app.py`
for actual production serving (e.g. behind a reverse proxy). Re-run
`npm run build` after any change under `web/src/` to pick it up here —
this mode serves whatever is currently in `web/dist/`, not live source.

A real generation needs the pipeline's own LLM endpoint configured first —
see the main README's [How to run it](../backend/code/artifacts/SYS5/README.md#how-to-run-it)
for the `SYS5_LLM_*` environment variables. Configuring a client (memory/
skills/subagents) works fine without one; only clicking Generate needs it.

## How it's built

- `app.py` — the FastAPI routes: reference data (`/api/config`), CRUD for
  a client's memory/skills/subagents (thin wrappers around `builders.py`),
  file upload, and the generate/status/download job endpoints. Stateless
  per request except the one global job dict. Mounts `web/dist/` (the
  built React app) at `/` once it exists, after every `/api/*` route so
  those always take priority — see the comment above that mount.
- `builders.py` — the only module that actually reads/writes files under
  `clients/<name>/`. Adds the SYS5 package to `sys.path` itself (it lives
  outside `backend/`, so this isn't automatic) and then reuses the
  pipeline's own validation directly — `sys5_agent.config.settings.
  validate_safe_name`, the real tool list from `sys5_agent.tools.
  excel_tools` — rather than duplicating any of it. No FastAPI dependency,
  so it's testable on its own.
- `web/` — the React dashboard (Vite + Tailwind CSS + Framer Motion +
  lucide-react), a separate project with its own `package.json`, talking
  to `app.py` purely over `/api/*`. See `web/README.md` for its internal
  structure.
- `test_app.py` — end-to-end regression test against a scratch `clients/`
  directory and a mocked `sys5()` (no real LLM needed) covering the CRUD
  endpoints, the upload → generate → poll → download lifecycle, and the
  single-job-at-a-time guard. Run with `python test_app.py` -- no Node/npm
  needed, it doesn't require `web/` to be built.
