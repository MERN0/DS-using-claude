"""
FastAPI app serving the client-customization chat UI.

This process only authors files under `clients/<name>/` (memory rules,
skill overrides, custom subagents) via `builders.py`/`state.py` -- it never
invokes `sys5()` or runs a real generation. Deliberate scope boundary, not
an oversight: see `README.md` in this directory.

Run with:
    pip install -r requirements.txt
    python app.py
then open http://localhost:5050/
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_FRONTEND_DIR = Path(__file__).resolve().parent
# This file lives in frontend/ at the repo root, a sibling of backend/ --
# not nested under the SYS5 package -- so the path to sys5_agent has to be
# spelled out rather than assumed to be this file's own parent directory.
_REPO_ROOT = _FRONTEND_DIR.parent
_SYS5_DIR = _REPO_ROOT / "backend" / "code" / "artifacts" / "SYS5"
if str(_SYS5_DIR) not in sys.path:
    sys.path.insert(0, str(_SYS5_DIR))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from fastapi.templating import Jinja2Templates  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402

import state  # noqa: E402

app = FastAPI(title="SYS5 Client Setup")
# A throwaway per-process default is fine here: this session only ever
# holds which client is being edited and an in-progress draft, nothing
# sensitive, and losing it just means starting the chat over. Set
# SYS5_UI_SECRET_KEY to something real for anything beyond local use.
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SYS5_UI_SECRET_KEY", os.urandom(24).hex()))
app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(_FRONTEND_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/start")
def api_start(request: Request):
    """Resets the conversation and returns the opening bot turn -- called
    once on page load, and again for "switch client" / "start over"."""
    request.session.clear()
    request.session.update(state.start_session())
    return JSONResponse(_run(request.session, {}))


@app.post("/api/chat")
async def api_chat(request: Request):
    if "step" not in request.session:
        return JSONResponse({"error": "Session expired -- refresh the page."}, status_code=400)
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 -- empty/non-JSON body is a valid "no input" turn
        payload = {}
    return JSONResponse(_run(request.session, payload or {}))


def _run(sess, payload: dict) -> dict:
    """Runs one state-machine turn, never letting a bug in one chat step
    crash the whole page -- the user just sees an error bubble and can
    keep going from the main menu instead of a broken request."""
    try:
        return state.process(sess, payload)
    except Exception as e:  # noqa: BLE001 -- see docstring
        sess["step"] = "main_menu" if sess.get("client") else "welcome"
        return {
            "messages": [f"Something went wrong on that step ({type(e).__name__}: {e}). Let's back up."],
            "kind": "buttons" if sess.get("client") else "text",
            "choices": state._MAIN_MENU_CHOICES if sess.get("client") else [],
            "placeholder": "",
            "prefill": "",
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("SYS5_UI_HOST", "127.0.0.1"),
        port=int(os.environ.get("SYS5_UI_PORT", "5050")),
    )
