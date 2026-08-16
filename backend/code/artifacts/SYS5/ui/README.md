# SYS5 Client Setup — chat UI

A small, self-contained Flask app for authoring a client's customizations
to the SYS2→SYS5 pipeline through a guided, chatbot-style conversation,
instead of hand-writing Markdown/YAML files under `clients/<name>/`.

See the main [architecture guide](../README.md) first if you haven't —
this UI is just an authoring front end for concepts explained there
(clients, skills, memory, subagents).

## What it does

Walks you through creating, editing, or deleting three kinds of
client-scoped customization, explaining each concept as it comes up:

- **Memory rules** (`clients/<name>/memory/AGENTS.md`) — a standing
  instruction always in effect for that client.
- **Skill overrides** (`clients/<name>/skills/<skill>/SKILL.md`) — replace
  one of the four baseline skills (or the domain-knowledge skill) with the
  client's own version.
- **Custom subagents** (`clients/<name>/subagents/<name>.md`) — an
  additional specialist the orchestrator can delegate to for that client,
  alongside the fixed six the pipeline always runs. Never a replacement
  for the six-phase pipeline, only an addition to it.

Every save is validated against exactly what the pipeline itself expects
(see `sys5_agent/agent/build.py` and `sys5_agent/agent/custom_subagents.py`)
— an unknown tool/skill name, a missing required field, or an unsafe
client/subagent name is rejected with an explanation before anything is
written, and a preview of the exact file content is always shown before
saving.

## What it deliberately does *not* do

This UI only authors files — it never calls `sys5()` or runs a real
generation. Testing a client's new configuration is still done the normal
way (the CLI or the backend's `sys5()` call, see the main README's
[How to run it](../README.md#how-to-run-it)). Keeping "author the
configuration" and "run a generation" as two separate, unconnected tools
is a deliberate scope boundary, not a missing feature — a real run can
take many minutes and needs LLM connectivity this UI has no reason to
depend on.

## Running it

```bash
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:5050/`. Set `SYS5_UI_PORT`/`SYS5_UI_HOST` to
change where it listens, and `SYS5_UI_SECRET_KEY` to pin the session
signing key across restarts (otherwise a random one is generated per
process start, which just means an in-progress conversation doesn't
survive a restart — nothing persisted to `clients/` is affected either
way). For production-style serving, run it with `uvicorn app:app` directly
instead (e.g. behind a reverse proxy) rather than the `python app.py`
dev-server entry point.

## How it's built

- `app.py` — the only FastAPI code: two routes (`/api/start`, `/api/chat`)
  plus the page itself, using Starlette's `SessionMiddleware` for a
  signed-cookie conversation session. Holds no business logic.
- `state.py` — the conversation as a step-name → handler-function state
  machine (see its own module docstring for the exact "bot turn" shape).
  Pure logic, no Flask dependency, so it's testable on its own.
- `builders.py` — the only module that actually reads/writes files under
  `clients/<name>/`. Every format guarantee lives here in one place,
  reusing the pipeline's own validation (`settings.validate_safe_name`,
  the real tool list from `tools/excel_tools.py`) rather than duplicating
  it.
- `templates/index.html` + `static/chat.js` + `static/style.css` —
  Bootstrap 5 (via CDN) for styling, vanilla JS for the chat interaction.
  The JS has zero knowledge of the conversation's shape — it renders
  whatever `state.py` says the current step needs (buttons, checkboxes,
  a single-line or multi-line text box) and posts the reply back.
