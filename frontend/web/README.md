# SYS5 dashboard — React frontend

The dashboard UI, as a React SPA (Vite + Tailwind CSS 4 + Framer Motion +
lucide-react). Talks to the FastAPI backend one directory up (`../app.py`)
purely over the REST endpoints defined there — this project has no
server-side code of its own and no other state.

## Structure

- `src/api.js` — the only place that calls `fetch()`; every backend
  endpoint used by the UI is one function here.
- `src/components/ui.jsx` — shared primitives (`Card`, `Button`, `Input`,
  `Select`, `Badge`, `Spinner`, ...) used by every panel, so the look stays
  consistent without a full component library dependency.
- `src/components/Toast.jsx` — a small toast notification system
  (`useToast()`) used for save/delete/error feedback instead of inline
  status text.
- `src/components/ClientPicker.jsx`, `TabNav.jsx` — the project picker and
  the four-tab shell.
- `src/components/MemoryPanel.jsx`, `SkillsPanel.jsx`,
  `SubagentsPanel.jsx`, `GeneratePanel.jsx` — one file per tab. Each of
  Memory/Skills/Subagents renders two layers: the read-only baseline
  that's already active for every client, and this client's own editable
  addition on top — see the main README for why that distinction matters.
- `src/App.jsx` — fetches `/api/config` once, owns which client/tab is
  selected, nothing else.

## Running it

```bash
npm install
npm run dev
```

This starts the Vite dev server (hot reload) on `http://localhost:5173/`
and proxies any `/api/*` request to the FastAPI backend on
`127.0.0.1:5050` (see `vite.config.js`) — so run `python ../app.py` in a
second terminal first.

For production, build static assets and let the backend serve them
directly (no separate frontend server, no proxy):

```bash
npm run build
cd .. && python app.py
```

`npm run build` writes to `dist/`, which `../app.py` mounts at `/` once it
exists (see `_WEB_DIST` there). Rebuild after any `src/` change to pick it
up in that mode.
