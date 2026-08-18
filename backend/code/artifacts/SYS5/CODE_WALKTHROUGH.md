# SYS5 Agent — Code Walkthrough

This is a **function-by-function, block-by-block companion** to
[`README.md`](./README.md). The README explains *what* the system does and
*why* it's built the way it is (architecture, diagrams, the two-filesystems
model, configuration reference). This document exists for a different job:
**reading the actual source and understanding what each function/block does
and why it's written that way**, file by file, in the order a run actually
executes them.

If a term here is unfamiliar (agent, subagent, tool, skill, memory,
`virtual_mode`, ...), read the README's
[Concepts glossary](./README.md#concepts-glossary) first — this document
assumes you already know what those words mean and focuses on the code.

## How to read this

Each section covers one file. Within a file, functions appear in the order
they're actually called during a run, not necessarily their order in the
file. Every function gets:

1. **What calls it, and when** — its place in the pipeline.
2. **The code** (verbatim excerpt, sometimes trimmed of long docstrings
   already covered by the README).
3. **A block-by-block walkthrough** — what each meaningful chunk of the
   function does and why, including the non-obvious "gotcha" reasoning
   behind it.

## Map of files, in execution order

```
sys5.py  or  main.py          (entry points — validate input, compute paths)
        |
agent/runner.py                run_pipeline() — the shared orchestration loop
        |
agent/build.py                 build_agent() — constructs everything the run needs
        |-- agent/prompts.py       (orchestrator's system prompt, imported)
        |-- agent/subagents.py     (the six fixed subagents, imported)
        |-- agent/custom_subagents.py  (a client's extra subagents, imported)
        |-- tools/excel_tools.py   (real-file IO tools, imported)
        |-- tools/mcp_tools.py     (optional MCP tools, imported)
        |-- config/settings.py     (every tunable value, imported everywhere)
        |
   deepagents.create_deep_agent()  <- the actual LangGraph agent is built here
        |
agent/runner.py again           agent.invoke(...) — runs the agent to completion
        |-- agent/progress.py        (ProgressLogger callback — live progress)
        |-- agent/logsink.py         (free-text line sink)
        |-- agent/run_events.py      (structured event sink + aggregator)
```

Everything below walks this same path, top to bottom.

---

## 1. Entry points

Two thin wrappers exist so there is exactly **one** implementation of the
generation cycle (`agent/runner.py`'s `run_pipeline`) behind both callers.

### 1.1 `backend/code/artifacts/SYS5/sys5.py` — the backend entry point

**Called by:** a real backend service, directly (`from ... import sys5;
sys5(...)`) — no subprocess, no CLI involved.

#### Bootstrap: making `sys5_agent` importable

```python
_PACKAGE_ROOT = Path(__file__).resolve().parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from sys5_agent.agent.runner import run_pipeline  # noqa: E402
from sys5_agent.config import settings  # noqa: E402
```

- `sys5_agent/` lives right next to this file, not on `sys.path` by default.
- `_PACKAGE_ROOT` is derived from `__file__`, not a hardcoded/assumed repo
  root — this is what lets the whole SYS5 pipeline be moved to a different
  location in the repo without touching this bootstrap.
- The `import` lines come *after* the `sys.path` mutation, which is why they
  carry `# noqa: E402` (ruff's "module level import not at top of file"
  rule — normally a real smell, deliberately suppressed here because the
  import genuinely cannot happen before the path fix).

#### `sys5(...)` — the public function

Takes eight keyword-only-in-spirit arguments (`domain`, `output_format`,
`project_name`, `username`, `current_version`, `input_folder_path`,
`output_folder_path`, `requirement_filename`) — see the README's
[How to run it](./README.md#how-to-run-it) for the full call example. Block
by block:

```python
input_dir = Path(input_folder_path).resolve()
if not input_dir.is_dir():
    raise FileNotFoundError(...)

requirements_path = input_dir / requirement_filename
if not requirements_path.is_file():
    raise FileNotFoundError(...)
```
Fails fast, before any agent/model cost is incurred, if the caller's paths
don't actually exist. These are the *only* two `FileNotFoundError`s this
function raises.

```python
normalized_domain = settings.normalize_domain(domain)
if normalized_domain not in settings.DOMAINS:
    raise ValueError(...)

normalized_format = str(output_format).strip().lower().lstrip(".")
if normalized_format not in settings.SUPPORTED_OUTPUT_FORMATS:
    raise ValueError(...)

settings.client_dir(project_name)  # raises ValueError for an unsafe name
```
Three independent validation steps:
- `normalize_domain` lowercases/trims and resolves known aliases (e.g.
  `"chasis"` → `"chassis"`) before checking membership in `settings.DOMAINS`.
- `output_format` is normalized the same way and checked against the
  (currently `["xlsx"]`-only) whitelist.
- `settings.client_dir(project_name)` is called **only for its side effect**
  of validating the name — see [§9](#9-configsettingspy) for
  `validate_safe_name`. The returned `Path` is discarded here; this call
  exists purely to reject a `project_name` like `"../../etc"` before it can
  ever be joined onto a real path anywhere downstream.

```python
output_dir = Path(output_folder_path).resolve()
output_dir.mkdir(parents=True, exist_ok=True)
safe_version = _VERSION_SAFE_RE.sub("_", str(current_version).strip()) or "v0"
output_path = output_dir / f"{project_name}_SYS5_{safe_version}.{normalized_format}"
```
- The output directory is created if missing (input directory is not —
  it's expected to already exist with real data in it).
- `_VERSION_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]+")` strips anything that
  isn't alphanumeric/`_`/`.`/`-` out of `current_version` before it becomes
  part of a filename — a version string like `"v3 (final!)"` becomes
  `"v3__final_"` rather than producing a broken/unexpected path. Falls back
  to `"v0"` if the sanitized result is empty.
- The **exact output path is computed here, before the agent is built** —
  this matters because `build_agent` (see §3) uses this exact `output_path`
  to construct a write tool that can *only* ever write to this one file.

```python
context_lines = [
    f"Project: {project_name}",
    f"Requested by: {username}",
    ...
    "Input files: call list_input_files() (no arguments) via the "
    "discovery-agent to enumerate them -- ...",
    f"Output path for the final workbook: {output_path}",
]

result = run_pipeline(
    client=project_name, domain=normalized_domain,
    input_dir=input_dir, output_path=output_path,
    context_lines=context_lines,
)
```
Builds the first user message the orchestrator will see, as a list of
plain-text lines — including one explicit reminder that the *only* correct
way to see input files is `list_input_files()`, not a generic filesystem
tool (this is the same warning baked into the orchestrator's own system
prompt, repeated here because task-message content is what a model actually
attends to most strongly at turn one). Then it calls the one shared
`run_pipeline` (§2).

```python
return {
    "success": result["output_exists"],
    "output_path": str(result["output_path"]),
    "run_dir": str(result["run_dir"]),
    "summary": result["summary"],
    "final_message": result["final_message"],
}
```
Maps `run_pipeline`'s internal dict shape onto the backend's public
contract — notably `"success"` here is `result["output_exists"]`, which (see
§2) is computed from an actual before/after file-modification-time
comparison, not a bare existence check.

### 1.2 `sys5_agent/main.py` — the CLI entry point

**Called by:** `python -m sys5_agent.main ...` or `python main.py ...`.

Structurally the same shape as `sys5.py`, with two differences worth
calling out:

```python
_PACKAGE_PARENT = Path(__file__).resolve().parent.parent
if str(_PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PARENT))
```
This adds the **parent** of `sys5_agent/` (not `sys5_agent/` itself, unlike
`sys5.py`) — because this file lives *inside* the package and needs
`import sys5_agent.agent.runner` to resolve regardless of whether it's
invoked as `python -m sys5_agent.main`, `python main.py`, or
`python sys5_agent/main.py` directly.

```python
def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", default=settings.DEFAULT_CLIENT_DIR_NAME, ...)
    parser.add_argument("--domain", required=True,
                         choices=sorted(settings.DOMAINS) + sorted(settings.DOMAIN_ALIASES), ...)
    parser.add_argument("--input-dir", required=True, ...)
    parser.add_argument("--requirements-file", required=True, ...)
    parser.add_argument("--output-path", default=None, ...)
    return parser.parse_args(argv)
```
`--domain`'s `choices` list includes both real domain keys *and* known
aliases (`chasis`), so `argparse` itself rejects an unrecognized domain
before `main()`'s own body runs, with a helpful auto-generated error.

`main(argv=None)` then:

1. Resolves `input_dir`, checks `requirements_path.is_file()` — same
   fail-fast as `sys5.py`, but here it `print()`s to `stderr` and
   `return`s an exit code (`2`) instead of raising, since this is a CLI.
2. Calls `settings.client_dir(args.client)` inside a `try/except ValueError`
   — same purpose as `sys5.py`'s validation call, but reported as a CLI
   error message rather than a raised exception. If the client directory
   just doesn't exist yet (as opposed to being an invalid name), it's only a
   `WARNING` — the run still proceeds on baseline rules alone.
3. Similarly warns (doesn't fail) if the chosen domain has no
   `domain-knowledge` skill directory yet.
4. Computes `output_path`: if `--output-path` wasn't given, defaults to
   `settings.OUTPUT_DIR / f"{client}_SYS5_{stamp}.xlsx"`, where `stamp` is
   **this function's own** UTC timestamp — not the run workspace's, because
   the run workspace doesn't exist yet at this point (it's created inside
   `build_agent`, called later via `run_pipeline`).
5. Builds `task_message_lines` (same shape/intent as `sys5.py`'s
   `context_lines`) and calls `run_pipeline`.
6. Prints the run directory, the parsed `run_summary.json` (pretty-printed
   JSON) if one exists, and either the output path (exit code `0`) or an
   error plus the orchestrator's final message (exit code `1`).

---

## 2. `agent/runner.py` — `run_pipeline()`

**Called by:** both entry points above, with identical semantics either
way. This is the one place that turns `(client, domain, input_dir,
output_path, context_lines)` into an actual generation run and a
structured result — see the README's
[Request lifecycle](./README.md#request-lifecycle-end-to-end) sequence
diagram for the bird's-eye view; this section is the block-by-block version
of the same flow.

```python
_CONTINUE_NUDGE = (
    "You stopped without finishing -- run_summary.json does not exist yet in "
    "the run workspace, ... Take the next concrete action ... -- do not just "
    "describe status again."
)
```
A module-level constant: the exact message re-sent to the orchestrator when
it stops before finishing (see the "auto-continue loop" block below).
Keeping it as one named constant (rather than inlining it) makes it easy to
find and tune independently of the loop logic that uses it.

### Step 1 — build everything

```python
agent, run_dir = build_agent(client, domain, input_dir, output_path)
run_events.emit({"type": "run_dir", "run_dir": str(run_dir)})
```
`build_agent` (§3) does all the expensive one-time setup (model, run
workspace, layered memory/skills, subagents, tools) and returns the ready
LangGraph agent plus this run's workspace directory. The `run_dir` is
emitted as a structured event **immediately**, not only in the dict this
function eventually returns — this is what lets a caller like
`frontend/app.py` know the workspace path while the (potentially
many-minutes-long) run is still in progress, for a live "inspect this run's
files" link.

### Step 2 — snapshot the output path's state *before* running

```python
pre_run_mtime = output_path.stat().st_mtime if output_path.exists() else None
```
Recorded now, deliberately before `agent.invoke(...)` is ever called. See
"Step 5" below for why this exists — it's the fix for a real bug class
(false-positive "success" reports).

### Step 3 — build the task message and the invoke config

```python
task_message = (
    "\n".join(context_lines) + "\n\nGenerate the SYS5 test case workbook for this run now, "
    "following your system instructions."
)
logsink.emit(f"Run workspace: {run_dir}")

invoke_config = {
    "configurable": {"thread_id": run_dir.name},
    "recursion_limit": 1000,
    "callbacks": [ProgressLogger()],
}
summary_path = run_dir / "run_summary.json"
```
- `context_lines` (built by the caller, §1) are joined with the fixed
  trailing instruction — `run_pipeline` itself never inspects their content,
  it's purely a pass-through of per-run identifying context.
- `thread_id=run_dir.name` is what makes this run's LangGraph checkpointer
  state addressable — sending a second message with the *same* `thread_id`
  continues the exact same conversation (see Step 4).
- `recursion_limit: 1000` raises LangGraph's default step-count ceiling —
  a real multi-phase run with many chunked extraction/resolution/drafting
  delegations can easily need more graph steps than LangGraph's conservative
  default allows.
- `callbacks: [ProgressLogger()]` is the one line that turns on all live
  progress reporting — see §10. Because `deepagents`' `task` tool forwards
  the parent's callbacks down into every subagent invocation, this single
  handler, registered only here, sees every tool call made anywhere in the
  entire run.
- `summary_path` is computed once — checking `summary_path.is_file()` is
  literally the orchestrator's own definition of "done" (see its prompt,
  §4, step 10), reused here as the loop's termination condition.

### Step 4 — the invoke / auto-continue loop

```python
crash_message: str | None = None
result: dict[str, Any] = {}
next_message = task_message
attempt = 0
while True:
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": next_message}]}, config=invoke_config)
    except Exception as e:  # noqa: BLE001 -- deliberately broad
        crash_message = f"Agent run raised {type(e).__name__}: {e}"
        logsink.emit(f"[{run_dir.name}] !!! run crashed: {crash_message}")
        break

    if summary_path.is_file():
        break

    attempt += 1
    if attempt > settings.MAX_AUTO_CONTINUE_TURNS:
        logsink.emit(f"[{run_dir.name}] !!! giving up after {attempt - 1} auto-continue attempt(s) ...")
        break

    logsink.emit(f"[{run_dir.name}] ... orchestrator stopped before finishing ... auto-continuing ...")
    run_events.emit({"type": "auto_continue", "attempt": attempt})
    next_message = _CONTINUE_NUDGE
```

This is the resilience mechanism the README's
[Run resilience](./README.md#run-resilience-crashes-and-premature-stops)
section explains conceptually — here's the actual control flow:

- **First iteration**: `next_message = task_message` (the real task).
  Every iteration after a stop-without-finishing instead sends
  `_CONTINUE_NUDGE` on the **same thread** — because `agent` was built with
  an `InMemorySaver` checkpointer keyed by this exact `thread_id` (see §3),
  this doesn't restart the conversation; it continues it with full history
  intact (what discovery found, which chunks extraction already processed,
  everything), so the model isn't re-explaining anything, just picking up
  where it stopped.
- **`except Exception`** (intentionally broad, flagged `# noqa: BLE001`):
  catches *anything* — including a bug inside `deepagents` itself (the
  README documents a real example: `FilesystemBackend` raising a bare
  `ValueError("Path traversal not allowed")` for a `..` in a path, which its
  own error handling doesn't catch). This is not retried — `crash_message`
  is set and the loop breaks immediately, because re-invoking into whatever
  just broke is more likely to repeat the failure than fix it.
- **`if summary_path.is_file(): break`**: the *only* success exit from this
  loop. The orchestrator's own prompt defines "done" this way, so this
  check is the runner's literal, code-level enforcement of that same
  definition.
- **The auto-continue budget**: `attempt` increments each time the agent
  returns *without* raising and *without* `run_summary.json` existing —
  i.e., the model ended its turn with a chatty status update instead of a
  tool call. Once `attempt > settings.MAX_AUTO_CONTINUE_TURNS` (default 8),
  the loop gives up rather than nudging forever against a genuinely stuck
  model.
- Both the give-up message and every retry attempt emit through
  `logsink.emit` (free text, always printed) — and each retry attempt *also*
  emits a structured `{"type": "auto_continue", "attempt": N}` event through
  `run_events`, which is what lets a UI show "auto-continue attempt 2/8"
  live instead of only appearing in the scrolling log text.

### Step 5 — compute the final result

```python
summary: dict | None = None
if summary_path.is_file():
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

final_message = crash_message
if final_message is None and result.get("messages"):
    final_message = result["messages"][-1].content

output_written_this_run = output_path.is_file() and (
    pre_run_mtime is None or output_path.stat().st_mtime != pre_run_mtime
)

return {
    "run_dir": run_dir, "output_path": output_path,
    "output_exists": output_written_this_run,
    "summary": summary, "final_message": final_message,
    "auto_continue_attempts": attempt,
}
```
- `summary` is the parsed `run_summary.json` if the loop actually reached
  it, `None` otherwise — callers treat `None` as its own failure signal.
- `final_message` prefers a crash message (if the loop broke via the
  `except` branch) over the orchestrator's own last message — so a caller
  always gets *some* explanation of what happened, whichever branch fired.
- **`output_written_this_run`** is the fix for the "reports success but
  nothing was actually written this run" bug class the README describes in
  detail (see
  [Output-file write safety](./README.md#output-file-write-safety)): a bare
  `output_path.is_file()` can't distinguish "this run just wrote it" from
  "a stale file from an earlier run of the same `project_name` +
  `current_version` happened to already be sitting there, and this run
  never actually got as far as writing." Comparing `st_mtime` against the
  value captured *before* `agent.invoke(...)` ran closes that gap.

---

## 3. `agent/build.py` — `build_agent()`

**Called by:** `run_pipeline`, once per run. This is the single most
consequential function in the codebase — it's where the model, the
sandboxed run workspace, the layered memory/skills, the subagents, and the
one write tool the orchestrator holds directly all come together into the
actual `deepagents` agent object.

### Helper: `_new_run_dir()`

```python
def _new_run_dir() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = settings.RUNS_DIR / stamp
    (run_dir / "memory").mkdir(parents=True, exist_ok=True)
    (run_dir / "skills").mkdir(parents=True, exist_ok=True)
    (run_dir / "resolved").mkdir(parents=True, exist_ok=True)
    return run_dir
```
Every run gets a fresh, timestamp-named directory under `sys5_agent/runs/`
— never reused. The three subdirectories it pre-creates
(`memory/`, `skills/`, `resolved/`) are exactly the ones the rest of
`build_agent` and the subagents need to exist up front; every other
workspace file (`discovery.md`, `requirements_index.jsonl`,
`clusters.jsonl`, `draft_testcases.jsonl`, `qa_report.md`,
`run_summary.json`) is created on demand by whichever subagent/orchestrator
step first writes it.

### Helper: `_write_layered_memory(run_dir, client, domain)`

```python
default_agents_md = settings.default_client_dir() / "memory" / "AGENTS.md"
client_agents_md = settings.client_dir(client) / "memory" / "AGENTS.md"

parts = []
if default_agents_md.is_file():
    parts.append(default_agents_md.read_text(encoding="utf-8"))

domain_label = settings.DOMAIN_LABELS.get(domain, domain)
parts.append(
    f"\n---\n\n# Domain for this run: {domain} ({domain_label})\n\n"
    "This run's automotive domain is fixed for the whole cycle -- ..."
)

if client != settings.DEFAULT_CLIENT_DIR_NAME and client_agents_md.is_file():
    parts.append(f"\n---\n\n# Client-specific rules: {client}\n\n" + client_agents_md.read_text(encoding="utf-8"))

(run_dir / "memory" / "AGENTS.md").write_text("\n".join(parts), encoding="utf-8")
```
Builds one concatenated `AGENTS.md` for this run by appending, in order:
1. The baseline rules (`clients/_default/memory/AGENTS.md`), if present —
   always first.
2. A synthetic paragraph (generated here, not read from any file) telling
   the model which domain this run is fixed to and pointing it at the
   `domain-knowledge` skill for details.
3. The client's own `AGENTS.md`, if this client has a directory *and* a
   memory file, appended last (so it reads as an addition on top of the
   baseline, not a replacement).

This is `deepagents`' `memory=` mechanism: unlike a skill, this file is
loaded into every turn's context automatically, for rules that must always
apply — see the README's
[Skills & memory layering](./README.md#skills--memory-layering).

### Helper: `_copy_skill_overrides(dest, skills_dir)`

```python
def _copy_skill_overrides(dest: Path, skills_dir: Path) -> None:
    if not skills_dir.is_dir():
        return
    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir():
            override_dest = dest / skill_dir.name
            if override_dest.exists():
                shutil.rmtree(override_dest)
            shutil.copytree(skill_dir, override_dest)
```
A small, reusable "layer these skill directories on top of what's already
in `dest`, replacing same-named ones" primitive. If `override_dest` (a
same-named skill already copied from an earlier, lower-priority layer)
already exists, it's removed first — `shutil.copytree` refuses to copy into
an existing directory otherwise. This is the literal mechanism behind "a
client skill overrides a same-named baseline/domain skill."

### Helper: `_copy_layered_skills(run_dir, client, domain)`

```python
def _copy_layered_skills(run_dir: Path, client: str, domain: str) -> None:
    dest = run_dir / "skills"

    default_skills = settings.default_client_dir() / "skills"
    if default_skills.is_dir():
        for skill_dir in default_skills.iterdir():
            if skill_dir.is_dir():
                shutil.copytree(skill_dir, dest / skill_dir.name, dirs_exist_ok=True)

    _copy_skill_overrides(dest, settings.domain_dir(domain) / "skills")

    if client != settings.DEFAULT_CLIENT_DIR_NAME:
        _copy_skill_overrides(dest, settings.client_dir(client) / "skills")
```
Three layers, applied in priority order (later wins):
1. **Baseline** (`clients/_default/skills/`) — the four always-loaded
   skills (`merging-strategy`, `writing-style`, `resolution-playbook`,
   `output-format`), copied with plain `copytree(..., dirs_exist_ok=True)`
   since `dest` starts empty for this layer.
2. **Domain** (`domains/<domain>/skills/`) — via `_copy_skill_overrides`,
   so it can replace a same-named baseline skill (it never does today,
   since `domain-knowledge` doesn't collide with any baseline skill name,
   but the mechanism supports it).
3. **Client** (`clients/<name>/skills/`) — same override mechanism,
   applied last, so a client's own skill wins over both prior layers.

### `build_agent(client, domain, input_dir, output_path)`

```python
domain = settings.normalize_domain(domain)
input_dir = Path(input_dir).resolve()
if not input_dir.is_dir():
    raise ValueError(f"input_dir does not exist or is not a directory: {input_dir}")
output_path = Path(output_path).resolve()

run_dir = _new_run_dir()
_write_layered_memory(run_dir, client, domain)
_copy_layered_skills(run_dir, client, domain)
mcp_tools = fetch_mcp_tools()
custom_subagents = load_custom_subagents(client, input_dir, run_dir, extra_tools=mcp_tools)
```
- Normalizes the domain and re-validates `input_dir` (a second check,
  independent of whatever the caller already did — `build_agent` doesn't
  trust its own callers not to have a bug).
- Creates the run workspace and writes its layered memory/skills — **in
  that order**, because `load_custom_subagents` (next line) validates each
  custom subagent's requested skill names against what's actually present
  under `run_dir/skills/`, so the skills must already be copied before this
  call.
- `fetch_mcp_tools()` (§8) is called **once per run**, not once per
  subagent — this is a deliberate anti-redundancy choice, since each call
  can launch real subprocesses (`uvx`, `npx`) and there's no reason to pay
  that cost more than once. It's a fast no-op (`return []` immediately)
  unless `settings.MCP_ENABLED` is set.
- `load_custom_subagents` (§6) merges those MCP tools into the same
  by-name lookup a client's custom subagent can select from, alongside the
  five built-in Excel tools.

```python
llm = ChatOpenAI(
    model=settings.LLM_MODEL,
    openai_api_key=settings.LLM_API_KEY,
    openai_api_base=settings.LLM_BASE_URL,
    temperature=settings.LLM_TEMPERATURE,
    profile={"max_input_tokens": settings.LLM_CONTEXT_TOKENS},
)
```
The `profile={"max_input_tokens": ...}` argument is the fix for a real
production crash — see the README's
[Context management](./README.md#context-management) section for the full
story (a self-hosted model name has no entry in `langchain_openai`'s
built-in profile registry, so without this, `deepagents`' auto-attached
summarization middleware falls back to a fixed 170k-token trigger that can
be *larger* than the endpoint's real limit, letting the conversation grow
past what the server will actually accept before compaction ever kicks in).
Every subagent inherits this same `llm` object (none of them override
`model` in their own definition — see §5), so this one fix covers the whole
run, not just the orchestrator.

```python
backend = FilesystemBackend(root_dir=str(run_dir), virtual_mode=True)
```
This is the *other* filesystem — see the README's
[The two filesystems](./README.md#the-two-filesystems). `virtual_mode=True`
sandboxes every built-in `ls`/`read_file`/`write_file`/`edit_file` tool call
(for the orchestrator and every subagent) to `run_dir`: no `..`, no
absolute path, nothing can ever resolve outside it, regardless of what the
model tries.

```python
agent = create_deep_agent(
    model=llm,
    tools=[build_write_tool(output_path)],
    system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    backend=backend,
    memory=["memory/AGENTS.md"],
    skills=["skills/"],
    subagents=build_subagents(input_dir) + custom_subagents,
    middleware=[TodoListMiddleware()],
    debug=settings.DEBUG,
    checkpointer=InMemorySaver(),
)

return agent, run_dir
```
The actual `deepagents` call. Field by field:
- `tools=[build_write_tool(output_path)]` — the orchestrator's **only**
  direct real-file tool, bound to exactly this run's output path (§7). No
  other real-file tool is given to the orchestrator itself; every read tool
  belongs to a subagent.
- `system_prompt=ORCHESTRATOR_SYSTEM_PROMPT` — see §4.
- `memory=["memory/AGENTS.md"]` / `skills=["skills/"]` — paths **relative
  to `backend`'s root** (i.e., relative to `run_dir`), pointing at the files
  `_write_layered_memory`/`_copy_layered_skills` just wrote.
- `subagents=build_subagents(input_dir) + custom_subagents` — the six fixed
  subagents (§5), with any client-specific ones appended (always additive,
  never a replacement — enforced by convention in the prompts, not by code
  here).
- **`middleware=[TodoListMiddleware()]`** — this is the fix for a second
  real gap, found by empirically inspecting the actual middleware stack
  `create_deep_agent` produces for a plain `ChatOpenAI` model: it does
  **not** include a todo/planning tool by default (that only happens
  automatically for specific OpenAI Codex harness profiles). Without this
  line, the orchestrator's prompt would reference a `write_todos` tool that
  doesn't actually exist. `middleware=` is additive — applied after
  `create_deep_agent`'s own base stack, before its tail middleware — and
  affects **only the orchestrator**; the six built-in subagents and any
  custom ones each build their own independent middleware stack from their
  own spec dict and do not inherit this.
- `checkpointer=InMemorySaver()` — this is what makes the auto-continue
  loop in `run_pipeline` (§2) actually able to resume the same conversation
  by `thread_id`, rather than starting fresh each time. It's in-memory
  only: it survives repeated `agent.invoke()` calls within this one running
  process, not a process restart.

---

## 4. `agent/prompts.py` — the orchestrator's system prompt

**Used by:** `build_agent`, as the literal `system_prompt=` string. This is
one big f-string (`ORCHESTRATOR_SYSTEM_PROMPT`), assembled once at import
time — every `{settings.X}` interpolation bakes the *current* config value
directly into the prompt text, so changing a setting (e.g.
`MAX_CLUSTER_BATCH_SIZE`) automatically updates what the model is told,
with no separate place to keep in sync.

The prompt has four sections, each covered in detail (with full rules
reproduced) in the README's [The orchestrator](./README.md#the-orchestrator)
and [Pipeline flow](./README.md#pipeline-flow) sections — this walkthrough
focuses on *how* the prompt is constructed, not repeating its full content:

1. **Role framing** — "you delegate every phase of real work... your own
   job is to plan the run... and only ever call `write_output_workbook`
   yourself once."
2. **"Two separate filesystems -- do not confuse them"** — the same
   distinction the README dedicates a whole section to, restated here in
   the model's own instructions because this is the single most common
   real failure mode this pipeline hits (see README:
   ["No input files found" troubleshooting entry](./README.md#troubleshooting--faq)).
3. **"Non-negotiable rules"** — every rule interpolates a live
   `settings.*` value (`{settings.QUALIFICATION_MARKERS}`,
   `{settings.CHECK_TYPES}`, `{len(settings.OUTPUT_COLUMNS)}` +
   `{settings.OUTPUT_COLUMNS}`, `{settings.MAX_REQS_PER_TESTCASE}`) rather
   than a hardcoded number/list, so the prompt can never drift from
   `config/settings.py`.
4. **"Recommended phase order"** — the ten-step checklist (see README's
   [Pipeline flow](./README.md#pipeline-flow) diagram for the visual
   version). Notable interpolations: step 2 references
   `{settings.REQUIREMENT_CHUNK_SIZE}`; steps 4 and 6 reference
   `{settings.MAX_CLUSTER_BATCH_SIZE}` and explicitly instruct **parallel**
   `task()` calls when independent batches are ready (this is the
   LLM-call-time optimization pass — batching several clusters per
   delegation, and running independent batches concurrently, cuts down the
   total number of subagent invocations for a run with many small
   clusters); step 8 explains the `retry_cluster_ids` QA-retry-scoping
   mechanism in the model's own words, matching what `qa-validation-agent`'s
   own prompt (§5) implements on the receiving end.
5. **"Working discipline"** — the closing section stating explicitly that
   the run isn't done until `run_summary.json` exists, that a
   conversational status update with no tool call ends the run right there
   (incomplete), and a cost-awareness note: stopping without a tool call
   triggers an *expensive* full-context auto-continue resumption (see §2),
   so taking one more concrete action is always cheaper than stopping and
   being nudged back in.

---

## 5. `agent/subagents.py` — the six fixed subagents

**Called by:** `build_agent`, once per run, via
`build_subagents(input_dir)`.

```python
_RETURN_SUMMARY_ONLY = (
    "Persist all detailed findings to a file in the run workspace (via "
    "write_file/edit_file) as instructed below. Return only a short "
    "summary to the caller: what you did, the workspace file(s) you wrote, "
    "and any counts/flags the orchestrator needs to decide what's next. "
    "Do not paste large tables or full row dumps back in your response."
)
```
A shared instruction string, appended to the end of **every** subagent's
`system_prompt`. This single sentence is the entire mechanism that keeps
the orchestrator's own context small no matter how large the input file
is — each subagent burns through detail in its own short-lived
conversation, then hands back one paragraph.

```python
def build_subagents(input_root: Path) -> list[dict]:
    list_input_files, list_workbook_sheets, preview_sheet, read_sheet_range, search_sheet = build_read_only_tools(
        input_root
    )
    ...
    return [discovery_agent, requirement_extraction_agent, merge_planning_agent,
            resolution_agent, test_case_drafting_agent, qa_validation_agent]
```
This is a **factory function**, not a static list — the five read-only
Excel tools are built once, here, bound to `input_root` (this run's real
input directory), and then handed out selectively to whichever subagents
need them. Each subagent is a plain Python `dict` with five keys: `name`,
`description` (what the *orchestrator* sees when deciding whether/when to
delegate), `system_prompt` (that subagent's own instructions once invoked),
`tools`, and `skills`.

The full text of each subagent's `description`/`system_prompt` is already
reproduced verbatim in the README's
["What each one actually does"](./README.md#what-each-one-actually-does)
section and the codebase itself — rather than re-paste ~400 lines of prompt
text a second time, this walkthrough highlights **what each subagent's
`tools`/`skills` lists actually are**, since that's the part that
determines what it's *capable* of doing, independent of what its prompt
tells it to do:

| Subagent | `tools` | `skills` | Why these specific tools |
|---|---|---|---|
| `discovery-agent` | `list_input_files`, `list_workbook_sheets`, `preview_sheet` | `domain-knowledge` | Enough to enumerate and classify every sheet by content — deliberately **no** `read_sheet_range`/`search_sheet`, since discovery only needs to *preview*, not deeply read. |
| `requirement-extraction-agent` | `read_sheet_range`, `preview_sheet` | `domain-knowledge` | `read_sheet_range` for the bounded chunk it was assigned; `preview_sheet` to re-check header/column meaning if needed. No `search_sheet` — it's not searching, it's reading a specific range. |
| `merge-planning-agent` | *(none)* | `merging-strategy`, `domain-knowledge` | Works entirely from `requirements_index.jsonl`/`resolved/*.md` already written to the run workspace — it never touches a real Excel file, so it gets zero Excel tools. |
| `resolution-agent` | `search_sheet`, `read_sheet_range`, `preview_sheet`, `list_workbook_sheets` | `resolution-playbook`, `domain-knowledge` | The only subagent with `search_sheet` — its entire job is finding exact signal/command names in supporting sheets without reading them in full. |
| `test-case-drafting-agent` | *(none)* | `writing-style`, `output-format`, `domain-knowledge` | Zero Excel tools, by design: it works only from what extraction/resolution already recorded in the workspace, so it **structurally cannot** introduce a signal/command that wasn't actually resolved — this is enforced by capability, not just instruction. |
| `qa-validation-agent` | *(none)* | `output-format` | Same reasoning as drafting — it cross-checks workspace files (`draft_testcases.jsonl`, `requirements_index.jsonl`, `clusters.jsonl`, `resolved/*.md`, `discovery.md`), never real Excel files directly. |

Every subagent's `system_prompt` ends with `+ _RETURN_SUMMARY_ONLY`, and
(this session's LLM-call-optimization pass) `resolution-agent` and
`test-case-drafting-agent`'s prompts explicitly describe **batch
processing**: "you're given one or more cluster_ids... process every
cluster you were given independently... each still gets its own separate
output file." This is what lets the orchestrator's phase-4/phase-6
delegations (per its own prompt, §4) group up to
`settings.MAX_CLUSTER_BATCH_SIZE` clusters into one `task()` call instead of
one call per cluster, cutting the number of LLM-backed delegations for a run
with many small clusters, without changing what gets produced (still one
`resolved/<cluster_id>.md` / one draft row per cluster either way).

`qa-validation-agent`'s prompt implements the **retry-scoping** mechanism:
if its task message includes `retry_cluster_ids`, it reads *only* those
clusters' `resolved/<cluster_id>.md` files (not every one) and scopes
checks (2)–(9) to just those clusters' rows — but checks (1) and (10)
(whole-run traceability coverage and extraction coverage) are explicitly
called out as **always** re-run against the full draft set regardless,
since a single cluster's fix can't be verified for whole-run coverage in
isolation. This is what fixed the redundancy the README's
[Configuration reference](./README.md#configuration-reference) alludes to:
previously, *every* QA retry re-read and re-checked the entire draft set,
up to `MAX_QA_RETRIES(2) + CRITICAL_MAX_RETRIES(3) = 5` times per run.

---

## 6. `agent/custom_subagents.py` — a client's extra subagents

**Called by:** `build_agent`, once per run, via
`load_custom_subagents(client, input_dir, run_dir, extra_tools=mcp_tools)`.

### File format

A custom subagent is one Markdown file at
`clients/<name>/subagents/<subagent-name>.md`, deliberately reusing the
same "YAML frontmatter + Markdown body" shape as a `SKILL.md` file rather
than inventing a new format:

```
---
name: extra-safety-checks-agent
description: One sentence the orchestrator reads to decide whether to
  delegate to this subagent, and when.
tools: [search_sheet, read_sheet_range]
skills: [domain-knowledge]
---

The subagent's own system prompt, as plain Markdown.
```

```python
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)
```
Public (not prefixed `_`) specifically so `frontend/builders.py` can import
and reuse this exact regex — the dashboard's authoring UI and this loader
can never drift apart on what counts as valid frontmatter.

### `_parse_subagent_file(path) -> dict | None`

```python
try:
    text = path.read_text(encoding="utf-8")
except OSError as e:
    print(f"[custom-subagents] skipping {path.name}: could not read file: {e}", flush=True)
    return None

match = FRONTMATTER_RE.match(text)
if not match:
    print(...); return None

try:
    front = yaml.safe_load(match.group(1)) or {}
except yaml.YAMLError as e:
    print(...); return None

if not isinstance(front, dict):
    print(...); return None

name = str(front.get("name") or "").strip()
description = str(front.get("description") or "").strip()
body = match.group(2).strip()

if not name or not description or not body:
    print(...); return None

tools_field = front.get("tools") or []
skills_field = front.get("skills") or []
if not isinstance(tools_field, list) or not isinstance(skills_field, list):
    print(...); return None

return {"name": name, "description": description,
        "system_prompt": body + _CONTRACT_REMINDER,
        "tool_names": [str(t).strip() for t in tools_field],
        "skill_names": [str(s).strip() for s in skills_field]}
```
Every failure path is the same shape: **print a warning, return `None`**,
never raise. This is a deliberate, consistently-applied philosophy (stated
in the module docstring): a malformed, missing, or partially-invalid custom
subagent file is never a reason to fail a whole run — the caller
(`load_custom_subagents`, below) just skips that one file. Five independent
things are checked, in order: the file is readable; it has a valid
`---`-delimited frontmatter block at all; the frontmatter parses as YAML;
the parsed YAML is a mapping (not e.g. a bare string or list); `name`,
`description`, and a non-empty body are all present; `tools`/`skills` (if
given) are lists.

The returned `system_prompt` is `body + _CONTRACT_REMINDER` — the contract
reminder (a fixed paragraph restating the non-negotiable output rules: no
invented signals, `SET`/`VERIFY` operators, Test Case ID assigned
automatically, persist detail and return a summary) is appended **at load
time**, never stored in the authored file itself. This means it can never
go stale or be accidentally edited out by whoever authors the file, and the
dashboard UI doesn't need to keep a second copy of this text in sync with
this one.

### `load_custom_subagents(client, input_root, run_dir, extra_tools=None) -> list[dict]`

```python
if client == settings.DEFAULT_CLIENT_DIR_NAME:
    return []
subagents_dir = settings.client_dir(client) / "subagents"
if not subagents_dir.is_dir():
    return []

tools_by_name = {t.name: t for t in build_read_only_tools(input_root)}
for t in extra_tools or []:
    tools_by_name[t.name] = t
run_skills_dir = run_dir / "skills"

out: list[dict] = []
seen_names: set[str] = set()
for path in sorted(subagents_dir.glob("*.md")):
    parsed = _parse_subagent_file(path)
    if parsed is None:
        continue

    if parsed["name"] in seen_names:
        print(...); continue

    tools = []
    for tool_name in parsed["tool_names"]:
        tool_obj = tools_by_name.get(tool_name)
        if tool_obj is None:
            print(...); continue
        tools.append(tool_obj)

    skills = []
    for skill_name in parsed["skill_names"]:
        if not (run_skills_dir / skill_name).is_dir():
            print(...); continue
        skills.append(skill_name)

    out.append({"name": parsed["name"], "description": parsed["description"],
                "system_prompt": parsed["system_prompt"], "tools": tools, "skills": skills})
    seen_names.add(parsed["name"])
    print(f"[custom-subagents] loaded '{parsed['name']}' from {path.name}", flush=True)

return out
```
Block by block:
- **Early-out for the default/baseline client** — `_default` never has
  custom subagents by definition.
- **Early-out if `subagents/` doesn't exist** — a project with no such
  directory yet still runs fine on the fixed six alone.
- **`tools_by_name`** merges the five built-in read-only Excel tools
  (rebuilt here, bound to `input_root` again — a second, independent
  instance from the one `build_subagents` built, but bound to the same real
  directory) with `extra_tools` (the MCP tools `build_agent` fetched, §8) —
  a client can request an MCP tool by name exactly like a built-in Excel
  tool, no separate mechanism needed on the authoring side.
- **The main loop**, for every `*.md` file in the client's `subagents/`
  directory, sorted (deterministic order, not filesystem-dependent):
  1. Parse it — skip (already logged inside `_parse_subagent_file`) if it
     fails any check.
  2. Reject a **duplicate name** within this same client — two files
     defining the same subagent name would be ambiguous about which one
     wins; this makes it an explicit, logged skip rather than a silent
     last-write-wins.
  3. Resolve each requested tool name against `tools_by_name` — an unknown
     name is dropped (with a warning) rather than treated as a reason to
     skip the whole subagent; the subagent still gets built with whatever
     valid tools it did request.
  4. Resolve each requested skill name against `run_skills_dir` — only a
     skill actually present under `run_dir/skills/` (i.e. one of the
     baseline/domain/client skills this run already layered in, per §3) is
     kept; a reference to a skill that was never copied into this run's
     workspace would be a dead reference, so it's dropped the same
     tolerant way.
  5. Append the finished subagent dict and log that it loaded successfully.

---

## 7. `tools/excel_tools.py` — every tool that touches a real file

**Called by:** `build_subagents` (read-only tools) and `build_agent`
(write tool) — see §3 and §5 for who receives which.

### The sandboxing primitive: `_resolve_within(root, file_name)`

```python
def _candidate_for(root: Path, raw: str) -> Path | None:
    candidate = Path(raw)
    candidate = candidate if candidate.is_absolute() else (root / candidate)
    candidate = candidate.resolve()
    if candidate != root and root not in candidate.parents:
        return None
    return candidate


def _resolve_within(root: Path, file_name: str) -> Path | None:
    root = root.resolve()
    candidate = _candidate_for(root, file_name)
    if candidate is not None and candidate.exists():
        return candidate

    tail = _PATH_SEP_RE.split(str(file_name).strip())[-1]
    if tail and tail != str(file_name):
        fallback = _candidate_for(root, tail)
        if fallback is not None and fallback.exists():
            return fallback

    return candidate
```
This is the function every read-only tool below calls first, and it's
worth understanding precisely:

1. `_candidate_for` joins `raw` onto `root` (unless it's already absolute),
   then **`.resolve()`s** it — which collapses any `..` and follows
   symlinks — and checks the result is either exactly `root` or has `root`
   as one of its parents. If not, it returns `None`: this single check is
   what makes `..` traversal *and* a symlink that points outside `root`
   both impossible, regardless of how creatively `raw` is constructed.
2. `_resolve_within` tries the candidate as given first. If that doesn't
   exist, it tries a **fallback**: split `file_name` on `/` or `\` and take
   just the last segment, then resolve *that* against `root`. This is what
   makes a stray path-like value (e.g. a model mistakenly sending
   `"input/Requirements.xlsx"` or a Windows-style
   `"C:\Users\...\Requirements.xlsx"`) degrade gracefully to "just try the
   bare filename" instead of failing outright — since every tool is
   supposed to receive a bare `file_name` in the first place (see the
   module docstring's explanation of why paths were removed entirely from
   the tool signatures).
3. If neither resolves to an existing file, the original (non-existent)
   candidate is returned — callers check `.exists()` themselves via
   `_open_workbook` (below), so returning a non-`None`-but-nonexistent path
   here vs. `None` for a truly out-of-bounds path are two different,
   distinguishable outcomes: `None` means "access denied" (`_access_denied`
   is returned to the model); a resolved-but-missing path means "not
   found" (a different, more specific error from `_open_workbook`).

### `_open_workbook(p) -> (Workbook | None, error_json | None)`

```python
if not p.is_file():
    return None, _dump({"error": f"Not a file: '{p.name}'. Call list_input_files() ..."})
if p.suffix.lower() not in _SUPPORTED_READ_SUFFIXES:
    return None, _dump({"error": f"'{p.name}' is not a supported workbook -- only {_SUPPORTED_READ_SUFFIXES} ..."})
try:
    return load_workbook(p, read_only=True, data_only=True), None
except Exception as e:  # noqa: BLE001
    return None, _dump({"error": f"Could not open '{p.name}': {e}"})
```
Centralizes what used to be an inconsistently-applied check: only
`list_workbook_sheets` used to guard against a non-`.xlsx`/`.xlsm` file
before this existed; `preview_sheet`, `read_sheet_range`, and
`search_sheet` called `load_workbook` unguarded, so any of them crashed the
whole tool call (and the subagent turn with it) if a model handed back
something like a `.jsonl` workspace file it confused for a real input file.
Now every read-only tool below shares this one gate. `read_only=True` uses
`openpyxl`'s streaming read mode (important for large sheets);
`data_only=True` reads cached formula *values* rather than formula strings.

### The five read-only tools (inside `build_read_only_tools(input_root)`)

All five are closures over `root = Path(input_root).resolve()`, captured
once when `build_read_only_tools` is called — this is the factory pattern:
the resulting tool functions physically cannot be pointed at a different
directory later, no matter what a model's arguments claim.

- **`list_input_files()`** — no arguments at all. Lists every
  `.xlsx`/`.xlsm` file directly in `root` (not recursive), returning
  `{"file_name", "size_bytes"}` per file. This is the *only* correct way to
  discover the client's real files (see the README's
  [two-filesystems](./README.md#the-two-filesystems) explanation).

- **`list_workbook_sheets(file_name)`** — resolves `file_name` via
  `_resolve_within`, opens it via `_open_workbook`, then for every sheet
  returns `{"sheet_name", "max_row", "max_col"}`. Also `print()`s a summary
  line (`[workbook] file.xlsx -> 'Sheet1': 404 rows, ...`) directly to the
  terminal — independent of the `ProgressLogger` callback (§10) — so the
  sheet's real size is visible the instant it's known, before any chunked
  read against it even starts.

- **`preview_sheet(file_name, sheet_name, n_rows=None)`** — reads the first
  `n_rows` (default `settings.SHEET_PREVIEW_ROWS`) rows of one sheet.
  Notable implementation detail:
  ```python
  for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=min(n, ws.max_row or 0)), start=1):
      cells = {}
      for col_idx, cell in enumerate(row, start=1):
          if cell.value is not None:
              cells[get_column_letter(col_idx)] = _cell_str(cell.value)
      rows_out.append({"row": row_idx, "cells": cells})
  ```
  Row and column identity come from **`enumerate()`**, not from the cell
  object's own `.row`/`.column` attributes. This is deliberate and
  documented as the fix for a real bug: `openpyxl`'s read-only mode
  represents a blank cell as an `EmptyCell` placeholder that has *neither*
  attribute — code that trusted a cell's own position used to crash
  outright on any row containing a blank cell, or silently report a row
  number of `null` whenever column A happened to be blank. `enumerate()`
  sidesteps this entirely because it never asks a cell what its own
  position is; the same pattern repeats identically in `read_sheet_range`
  and `search_sheet` below.

- **`read_sheet_range(file_name, sheet_name, start_row, end_row,
  columns=None)`** — the workhorse for bounded chunked reads:
  ```python
  max_row = ws.max_row or 0
  requested_end = min(end_row, max_row)
  capped_end = min(requested_end, start_row + settings.MAX_ROWS_PER_READ - 1)
  truncated = capped_end < requested_end
  ```
  The requested range is clamped twice: once against the sheet's real
  `max_row` (can't read past the end), once against
  `settings.MAX_ROWS_PER_READ` (a hard server-side cap, independent of
  whatever range the model asked for — this is what actually protects the
  context budget regardless of what a model requests). `truncated` tells
  the caller whether it got less than it asked for, so it knows to page
  through with a follow-up call. The response also carries
  **`sheet_max_row`** (the sheet's true total row count) — this is what
  lets `requirement-extraction-agent` itself (not just a human watching the
  terminal) reason about how much of the sheet it still has left to cover.
  Also `print()`s `[read_sheet_range] file.xlsx::Sheet1 rows 41-80 of 404
  total` — same "visible in the terminal the instant it's known" pattern as
  `list_workbook_sheets`.

- **`search_sheet(file_name, sheet_name, query, columns=None,
  regex=False, max_results=None)`** — how resolution finds a signal/command
  without scanning hundreds of rows by hand:
  ```python
  if regex:
      pattern = re.compile(query, re.IGNORECASE)
      def matcher(text: str) -> bool:
          return pattern.search(text) is not None
  else:
      needle = query.lower()
      def matcher(text: str) -> bool:
          return needle in text.lower()
  ```
  Two named local functions (not `lambda`s — this was a Phase 0 formatting
  cleanup: `ruff`'s `E731` rule flags a `lambda` assigned to a name, and
  `matcher` needed to close over either `pattern` or `needle` depending on
  the `regex` flag, so two small named functions replaced the two
  lambda-assignment statements this file used to have). The scan itself
  iterates every row once, checking every populated cell (respecting
  `columns` if given) against `matcher`, collecting up to `limit`
  (`max_results` or `settings.MAX_SEARCH_RESULTS`) matches and setting
  `truncated=True` if more existed.

### The write tool: `build_write_tool(output_path)` → `write_output_workbook(rows)`

Also a factory — `out = Path(output_path).resolve()` is captured once, so
the tool has **no path argument at all** in its actual signature; there is
nothing for the model to get wrong about where this writes.

```python
wb = Workbook()
ws = wb.active
ws.title = settings.OUTPUT_SHEET_NAME
ws.append(settings.OUTPUT_COLUMNS)

id_col_idx = settings.OUTPUT_COLUMNS.index("Test Case ID")
warnings: list[str] = []
for i, row in enumerate(rows):
    lookup = {str(k).strip().lower(): v for k, v in row.items()}
    line = []
    missing = []
    for col in settings.OUTPUT_COLUMNS:
        key = col.strip().lower()
        if key in lookup:
            line.append(lookup[key])
        else:
            line.append("")
            missing.append(col)
    line[id_col_idx] = f"{settings.TEST_CASE_ID_PREFIX}{i + 1}"
    if "Test Case ID" in missing:
        missing.remove("Test Case ID")
    if missing:
        warnings.append(f"Row {i + 1}: missing columns {missing}, written blank")
    ws.append(line)
```
- The header row is written from `settings.OUTPUT_COLUMNS` directly —
  never from whatever keys the caller's `rows` happened to use.
- For each row, `lookup` is a case/whitespace-normalized dict of the
  caller's keys, so a row using `"test case id"` or `" Test Case ID "`
  still matches the canonical `"Test Case ID"` column name.
- **Every row's `"Test Case ID"` value is unconditionally overwritten**
  with `f"{prefix}{i + 1}"` in final row order — this is the *one* place
  in the whole pipeline that can guarantee both a fixed format and
  uniqueness across the entire file, rather than relying on every
  independent, possibly-parallel drafting call to avoid colliding with
  IDs it has no visibility into.
- Any column not present in a given row is written blank and recorded in
  `warnings` — except `"Test Case ID"` itself, which is removed from
  `missing` right after being force-assigned, since it can never actually
  be "missing" by the time this runs.

```python
tmp_path = out.parent / f".{out.stem}.{uuid.uuid4().hex}{out.suffix}"
try:
    wb.save(tmp_path)
    verify_wb = load_workbook(tmp_path, read_only=True)
    try:
        verify_ws = verify_wb[settings.OUTPUT_SHEET_NAME]
        if verify_ws.max_row != len(rows) + 1:
            raise ValueError(f"Saved workbook has {verify_ws.max_row} row(s), expected {len(rows) + 1} ...")
    finally:
        verify_wb.close()
    os.replace(tmp_path, out)
except Exception as e:
    tmp_path.unlink(missing_ok=True)
    return _dump({"error": f"Failed to save output workbook to {out}: {e}"})

return _dump({"output_path": str(out), "row_count": len(rows), "warnings": warnings})
```
The atomic-write sequence the README's
[Output-file write safety](./README.md#output-file-write-safety) section
explains conceptually — here's the exact five steps:
1. Save to a **temp file in the same directory** as `out` (same
   filesystem — required for the final `os.replace` to be atomic), named
   with a random hex suffix so it can never collide with a real output
   file or another concurrent run.
2. **Re-open that temp file** (not the in-memory `wb` object) and verify
   its row count actually matches what was written — catching a save that
   silently truncated.
3. **`os.replace(tmp_path, out)`** — an atomic rename: either it fully
   succeeds, or the original destination is left completely untouched.
   There is no window where a half-written file could sit at the real
   path.
4. On **any** exception across this whole sequence, the temp file is
   deleted and the function returns `{"error": ...}` — never lets an
   exception propagate out of the tool call, so the orchestrator sees a
   clear, structured failure it can react to (per its own prompt: retry
   once, then report honestly) instead of an opaque crash.
5. On success, returns `{"output_path", "row_count", "warnings"}` — the
   orchestrator's prompt explicitly tells it to check for the `"error"`
   key rather than assuming success just because the call returned.

---

## 8. `tools/mcp_tools.py` — optional MCP tools

**Called by:** `build_agent`, once per run, via `fetch_mcp_tools()`.

```python
MCP_SERVERS: dict[str, dict[str, Any]] = {
    "fetch": {
        "transport": "stdio", "command": "uvx",
        "args": ["--with", "mcp>=1.24.0,<2.0.0", "mcp-server-fetch"],
    },
    "sequential-thinking": {
        "transport": "stdio", "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
    },
}
```
A **fixed, code-reviewed allowlist** — unlike every other tool in this
codebase, an MCP server process gets whatever filesystem/network scope its
own process declares (there's no `_resolve_within`-style sandbox possible
for an arbitrary external server), so this dict is deliberately the *only*
place a server can be added, never something a client or the UI supplies
at runtime. The `mcp>=1.24.0,<2.0.0` pin on the `fetch` server's own
command line (not just in `requirements.txt`) exists because `uvx`
resolves its own isolated environment per invocation, independent of
whatever's pip-installed in this process — `mcp==2.0.0` is a breaking
rewrite the rest of the ecosystem (including `langchain-mcp-adapters`)
hasn't caught up to, discovered by direct testing during this feature's
implementation.

```python
async def _fetch_mcp_tools_async() -> list:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(MCP_SERVERS)
    tools: list = []
    for name in MCP_SERVERS:
        try:
            server_tools = await asyncio.wait_for(
                client.get_tools(server_name=name), timeout=settings.MCP_TOOL_TIMEOUT_SECONDS
            )
        except Exception as e:  # noqa: BLE001
            print(f"[mcp-tools] '{name}' unavailable, skipping: {type(e).__name__}: {e}", flush=True)
            continue
        tools.extend(server_tools)
        print(f"[mcp-tools] loaded {len(server_tools)} tool(s) from '{name}'", flush=True)
    return tools
```
The `langchain_mcp_adapters` import is **inside** the function, not at
module load time — this is what makes `mcp_tools.py` safe to import even
in an environment that never installed those optional dependencies (the
module itself has zero import-time cost when MCP is unused). Each server
is tried **independently**, with its own `asyncio.wait_for` timeout — a
server that fails to start (missing `uv`/Node, a network hiccup fetching
the package, a timeout) is logged and `continue`d past, never allowed to
fail the whole fetch, mirroring `custom_subagents.py`'s "one bad thing
never fails a whole run" philosophy.

```python
def fetch_mcp_tools() -> list:
    if not settings.MCP_ENABLED:
        return []
    try:
        return asyncio.run(_fetch_mcp_tools_async())
    except Exception as e:  # noqa: BLE001
        print(f"[mcp-tools] failed to fetch MCP tools, continuing without them: {type(e).__name__}: {e}", flush=True)
        return []
```
The synchronous entry point `build_agent` actually calls. Two layers of
safety: an instant `[]` if the feature is off at all (the common case —
default is off), and a second broad `except` around the whole
`asyncio.run()` call as a last-resort backstop (on top of the
per-server `try/except` inside `_fetch_mcp_tools_async` itself) — MCP
tooling is explicitly optional, so nothing here is allowed to fail a real
generation run. `asyncio.run()` is safe to call here specifically because
`build_agent()` is never itself called from inside an already-running
event loop in this codebase today (both the CLI's `main()` and
`frontend/app.py`'s background `threading.Thread` start with no active
loop) — flagged in the docstring as a fragile assumption worth re-checking
if that call site ever changes, since `asyncio.run()` raises loudly (not a
silent hang) if it ever stops holding.

```python
def available_mcp_tool_names() -> dict[str, str]:
    return {
        "fetch": "Fetch a URL from the internet and read its contents ...",
        "sequentialthinking": "A structured scratchpad for multi-step reasoning ...",
    }
```
A separate, **static** dict (not derived from `MCP_SERVERS`) used only by
`frontend/builders.py`'s `available_tools()` to populate the dashboard's
"Tools it can use" checkbox list — it always returns the full curated set
regardless of `MCP_ENABLED`, so a client can see and select these tools in
the UI even before an operator turns the feature on; the run itself simply
won't have them available until it is. (Note the actual tool *name* the
sequential-thinking MCP server exposes is `sequentialthinking`, no
hyphen — differs from its server *key* `sequential-thinking`, which the
server itself defines; this dict's keys match what a client would actually
type into a subagent's `tools:` frontmatter list.)

---

## 9. `config/settings.py` — every tunable value, in one place

Already has a complete reference table in the README's
[Configuration reference](./README.md#configuration-reference) — this
section covers the **functions**, which the README table doesn't detail.

### `validate_safe_name(name, label) -> str`

```python
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")

def validate_safe_name(name: str, label: str) -> str:
    name = str(name).strip()
    if not name or not _SAFE_NAME_RE.match(name) or ".." in name:
        raise ValueError(f"Invalid {label} {name!r}: must contain only letters, digits, '_', '-', '.' (no path separators, no '..').")
    return name
```
The **hard security backstop** against path traversal — used by
`client_dir()` and `domain_dir()` (below) before either ever joins the
given name onto `CLIENTS_DIR`/`DOMAINS_DIR`. It's intentionally lenient in
*shape* (allows underscores, dots, mixed case) because its job is purely to
reject something that could escape a directory join (a leading `/`, a `..`
segment, a path separator) — not to enforce a naming style. The explicit
`".." in name` check exists on top of the regex because `_SAFE_NAME_RE`
alone would actually already reject a bare `".."` (it doesn't start with
an allowed first character after trimming in most real cases) but the
extra check makes the intent unambiguous and defends against any future
regex tweak accidentally loosening that.

### `validate_kebab_name(name, label, *, min_len=2, max_len=64, require_suffix=None) -> str`

```python
_KEBAB_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

def validate_kebab_name(name, label, *, min_len=2, max_len=64, require_suffix=None) -> str:
    name = validate_safe_name(name, label)
    problems = []
    if not (min_len <= len(name) <= max_len):
        problems.append(f"{min_len}-{max_len} characters")
    if not _KEBAB_NAME_RE.match(name):
        problems.append("lowercase letters, digits, and single hyphens only (no underscores, dots, or CAPS)")
    if require_suffix and not name.endswith(require_suffix):
        problems.append(f"must end with {require_suffix!r} (e.g. 'extra-safety-checks{require_suffix}')")
    if problems:
        raise ValueError(f"Invalid {label} {name!r}: " + "; ".join(problems) + ".")
    return name
```
The **stricter, UX-facing convention** layered on top of the security
backstop above (`validate_safe_name` is always called first, unconditionally
— defense in depth, never bypassed). Three independent checks accumulate
into one combined error message rather than failing on the first problem,
so a caller sees everything wrong with a name in one round-trip instead of
fixing issues one at a time. `require_suffix` is how
`frontend/builders.py`'s `validate_subagent_name` enforces the `-agent`
suffix convention (matching the six built-in subagents' own naming) without
this function needing to know anything about subagents specifically —
it's a generic, reusable name-validation primitive. Deliberately **not**
applied inside `client_dir()`/`domain_dir()` themselves (see next), so an
existing client/domain whose name predates this convention keeps working;
this is a creation-time UX convention, not a retroactive restriction.

### `client_dir`, `default_client_dir`, `domain_dir`, `normalize_domain`

```python
def client_dir(client: str) -> Path:
    return CLIENTS_DIR / validate_safe_name(client, "client/project name")

def default_client_dir() -> Path:
    return CLIENTS_DIR / DEFAULT_CLIENT_DIR_NAME

def normalize_domain(domain: str) -> str:
    key = domain.strip().lower()
    return DOMAIN_ALIASES.get(key, key)

def domain_dir(domain: str) -> Path:
    return DOMAINS_DIR / validate_safe_name(normalize_domain(domain), "domain")
```
Small, deliberately dumb path helpers — every one of them routes through
`validate_safe_name` before ever constructing a `Path`, so **there is no
code path anywhere in this codebase that joins an unvalidated
client/domain name onto a real directory.** None of them check the
directory actually *exists* — that's left to callers (e.g. `main.py`
prints a `WARNING` and proceeds on baseline rules if a client directory
is missing; `build_agent`'s helpers use `.is_dir()`/`.is_file()` guards
before reading). `domain_dir` does **not** check that `domain` is one of
the recognized `DOMAINS` — that's a separate, explicit check callers do
themselves (`sys5.py`, `main.py`) when they need a hard "unsupported
domain" error rather than just a missing directory.

---

## 10. Live progress plumbing — `logsink.py`, `progress.py`, `run_events.py`

These three files exist for one reason: `agent.invoke(...)` is a single
blocking call from `run_pipeline`'s point of view — without them, nothing
would be visible between "Starting agent run..." and the final result,
even though a real run can spend many minutes and make dozens of nested
tool calls. Rather than restructure the whole pipeline into a streaming
loop, a `BaseCallbackHandler` is attached once to the top-level
`agent.invoke(...)` call (`agent/runner.py`'s `invoke_config`), and because
`deepagents`' own `task` tool explicitly forwards the parent's callbacks
down into every subagent invocation, that one handler sees every tool call
made **anywhere** in the run — the orchestrator's own, and every
subagent's — without any code here needing to know about subagent nesting
at all.

### `agent/logsink.py` — free-text lines

```python
_sink: Callable[[str], None] | None = None

def set_sink(sink: Callable[[str], None] | None) -> None:
    global _sink
    _sink = sink

def emit(line: str) -> None:
    print(line, flush=True)
    if _sink is not None:
        _sink(line)
```
As simple as it looks: `emit()` **always** prints to stdout (this is what
makes the CLI's live output work, unchanged, with zero CLI-side code) and
*additionally* forwards to `_sink` if one is registered. A caller that
wants to capture the same lines (e.g. `frontend/app.py`, for a
live-progress web UI) calls `set_sink(callback)` before starting a run and
`set_sink(None)` once it finishes. The module docstring is explicit that
this is **process-wide, not per-thread or per-run** — it only works
correctly because the pipeline currently supports at most one generation
running at a time in a given process (`frontend/app.py`'s single-job
design); if that assumption ever changes, this needs to become
`contextvars`-based instead so each concurrent run's lines route to its
own sink.

### `agent/run_events.py` — structured events

Same `set_sink`/`emit` shape as `logsink.py`, but carrying typed `dict`
events instead of text lines, and — critically — **nothing here ever
touches stdout**. If no sink is registered, an emitted event is simply
dropped (the same tradeoff `logsink` makes in reverse: `logsink` always
prints and optionally forwards; `run_events` never prints and only ever
forwards). This is a deliberately separate, parallel mechanism from
`logsink` rather than an extension of it, because the two serve different
consumers: `logsink` is for a human tailing a log; `run_events` is for a
caller that wants to render live *structured* UI (a todo checklist, a
"currently running: X" banner, per-skill/subagent usage counts) without
parsing text.

### `RunStateAggregator` — folding events into one live snapshot

```python
class RunStateAggregator:
    def __init__(self) -> None:
        self._run_dir: str | None = None
        self._todos: list[dict[str, str]] = []
        self._current_phase: dict[str, str] | None = None
        self._subagent_usage: dict[str, dict[str, float]] = {}
        self._skill_usage: dict[str, dict[str, int]] = {}
        self._auto_continue_attempts = 0

    def _subagent_bucket(self, name: str) -> dict[str, float]:
        return self._subagent_usage.setdefault(name, {"calls": 0, "total_seconds": 0.0, "errors": 0})

    def handle(self, event: dict[str, Any]) -> None:
        etype = event.get("type")
        if etype == "run_dir":
            self._run_dir = event.get("run_dir")
        elif etype == "todos":
            self._todos = event.get("todos") or []
        elif etype == "phase_start":
            subagent = event.get("subagent", "?")
            self._current_phase = {"subagent": subagent, "description": event.get("description", "")}
            self._subagent_bucket(subagent)["calls"] += 1
        elif etype == "phase_end":
            self._current_phase = None
            subagent = event.get("subagent", "?")
            self._subagent_bucket(subagent)["total_seconds"] += float(event.get("elapsed") or 0)
        elif etype == "phase_error":
            self._current_phase = None
            subagent = event.get("subagent", "?")
            bucket = self._subagent_bucket(subagent)
            bucket["total_seconds"] += float(event.get("elapsed") or 0)
            bucket["errors"] += 1
        elif etype == "skill_read":
            skill = event.get("skill")
            if skill:
                self._skill_usage.setdefault(skill, {"reads": 0})["reads"] += 1
        elif etype == "auto_continue":
            self._auto_continue_attempts = event.get("attempt", self._auto_continue_attempts)
        # Unknown event types are ignored rather than raised.

    def snapshot(self) -> dict[str, Any]:
        return {"run_dir": self._run_dir, "todos": list(self._todos),
                "current_phase": self._current_phase,
                "subagent_usage": {k: dict(v) for k, v in self._subagent_usage.items()},
                "skill_usage": {k: dict(v) for k, v in self._skill_usage.items()},
                "auto_continue_attempts": self._auto_continue_attempts}
```
`handle()` is a stateful fold — each event type updates exactly the piece
of state it's relevant to:
- `"todos"` **replaces** `self._todos` wholesale (never diffed/merged) —
  because `write_todos` (the underlying `deepagents` tool) always sends the
  orchestrator's full current list, never a partial delta, so replacing is
  correct, not a simplification.
- `"phase_start"`/`"phase_end"`/`"phase_error"` update `_current_phase`
  (set on start, cleared on end/error — this is the live "currently
  running: X" banner's data source) *and* accumulate into that subagent's
  usage bucket via `_subagent_bucket` — `calls` increments on start,
  `total_seconds` accumulates on end/error, `errors` increments only on
  error. A subagent's bucket is created lazily via `setdefault` the first
  time it's ever referenced, so usage stats naturally cover exactly the
  subagents actually invoked this run, nothing pre-populated.
- `"skill_read"` increments a per-skill read counter, same lazy-`setdefault`
  pattern.
- Any event type not listed above is silently ignored — the trailing
  comment states explicitly this must never be the reason a real
  generation run fails, mirroring the same tolerance philosophy as
  `custom_subagents.py`.

`snapshot()` returns a **fresh, defensively-copied dict** every call (note
`list(self._todos)` and the dict-comprehensions rebuilding nested dicts) —
this is what makes it safe for a caller (`frontend/app.py`) to hand the
snapshot straight into a JSON response without any risk of a later
`.handle()` call mutating something the caller already returned.

### `agent/progress.py` — `ProgressLogger`, the callback that drives both sinks

```python
class ProgressLogger(BaseCallbackHandler):
    def __init__(self) -> None:
        self._task_calls: dict[UUID, tuple[str, float]] = {}
        self._other_calls: dict[UUID, float] = {}
```
Two dicts keyed by LangChain's per-call `run_id` (a `UUID`), tracking
in-flight calls so `on_tool_end`/`on_tool_error` can look up what
`on_tool_start` recorded for the *same* call, even with multiple tool
calls in flight concurrently (e.g. parallel `task()` batch delegations).
`_task_calls` and `_other_calls` are tracked separately because only
`task` calls (subagent delegations) get the special "phase" treatment
below — a plain tool call just gets a compact one-line log entry.

```python
def on_tool_start(self, serialized, input_str, *, run_id, inputs=None, **kwargs) -> None:
    name = (serialized or {}).get("name") or "tool"
    args = inputs if inputs is not None else {"input": input_str}

    if name == "task":
        subagent_type = args.get("subagent_type", "?")
        description = args.get("description", "")
        self._task_calls[run_id] = (subagent_type, time.monotonic())
        logsink.emit(f"[{_timestamp()}] >>> delegating to {subagent_type}: {_truncate(description)}")
        run_events.emit({"type": "phase_start", "subagent": subagent_type, "description": description})
        return

    if name == "write_todos":
        run_events.emit({"type": "todos", "todos": args.get("todos") or []})
    elif name == "read_file":
        file_path = str(args.get("file_path") or "")
        if file_path.startswith(_SKILLS_PREFIX):
            skill_name = file_path[len(_SKILLS_PREFIX):].split("/", 1)[0]
            if skill_name:
                run_events.emit({"type": "skill_read", "skill": skill_name})

    self._other_calls[run_id] = time.monotonic()
    logsink.emit(f"[{_timestamp()}]     {name}({_truncate(args)})")
```
Three branches, in order of specificity:
1. **`name == "task"`** — a subagent delegation. Records
   `(subagent_type, start_time)` keyed by `run_id`, emits a distinctive
   `">>> delegating to X: ..."` log line, and emits a structured
   `phase_start` event — then **returns early**, skipping the generic
   logging path below (a `task` call gets its own two-line treatment, not
   the generic one-liner).
2. **`name == "write_todos"`** — emits the *entire* current todo list as a
   structured event (see `RunStateAggregator.handle` above for why a full
   replacement, not a diff, is correct here) — but does **not** return
   early, so it still falls through to the generic log line below too.
3. **`name == "read_file"`** whose `file_path` starts with `"skills/"` —
   parses out just the skill name (the path segment right after the
   `skills/` prefix, whether the full path is `"skills/<name>/SKILL.md"` or
   just `"skills/<name>"`) and emits a `skill_read` event. Also falls
   through to the generic logging below.

Every call, regardless of branch, ends up logged via `logsink.emit` — the
`task` branch gets a custom-formatted line and returns before reaching the
generic one; everything else (including `write_todos`/`read_file` after
their special-case structured-event handling) reaches the shared
`logsink.emit(f"... {name}({_truncate(args)})")` line at the bottom.

```python
def on_tool_end(self, output, *, run_id, **kwargs) -> None:
    task_entry = self._task_calls.pop(run_id, None)
    if task_entry is not None:
        subagent_type, started_at = task_entry
        elapsed = time.monotonic() - started_at
        summary = getattr(output, "content", output)
        logsink.emit(f"[{_timestamp()}] <<< {subagent_type} finished in {elapsed:.1f}s: {_truncate(summary)}")
        run_events.emit({"type": "phase_end", "subagent": subagent_type, "elapsed": elapsed})
        return
    self._other_calls.pop(run_id, None)
```
Looks up `run_id` in `_task_calls` first (via `.pop`, so the entry is
removed either way) — if found, this was a `task` call ending: computes
elapsed wall-clock time, logs a `"<<< X finished in Ns: <summary>"` line
(the summary is the subagent's own returned content — exactly the short
paragraph `_RETURN_SUMMARY_ONLY` instructs every subagent to produce),
emits the matching `phase_end` event, and returns. Otherwise, it was a
plain tool call — just pop it from `_other_calls` with nothing further to
log (no dedicated "end" line for ordinary tool calls; only `task` calls get
before/after pairs, since ordinary tool calls are already logged fully on
`on_tool_start`).

`on_tool_error` mirrors `on_tool_end`'s structure exactly, but for a
`task` call that raised: logs a `"!!! X FAILED after Ns: <error>"` line
and emits a `phase_error` event (which, per `RunStateAggregator.handle`,
still accumulates elapsed time into that subagent's usage bucket *and*
increments its `errors` counter) — a non-`task` tool error instead falls
through to a generic `"!!! tool error: ..."` line with no structured event
at all (tool-level errors that aren't a subagent delegation aren't tracked
in per-subagent usage stats today).

---

## Reading order, tied to the pipeline phases

If you want to trace one real run from the first line of code executed to
the last, in the exact order things happen, follow this list — each item
names the file/function and, in parentheses, the section above that covers
it in detail:

1. **Caller validates input, computes paths** — `sys5.py`'s `sys5()` or
   `main.py`'s `main()` (§1).
2. **`run_pipeline()` starts** — `agent/runner.py` (§2), which immediately
   calls `build_agent()`.
3. **Everything is constructed** — `agent/build.py`'s `build_agent()`
   (§3): run workspace created, memory/skills layered and copied, MCP
   tools fetched (§8), custom subagents loaded (§6), the model built with
   its context-window fix, the sandboxed `FilesystemBackend`, and finally
   `create_deep_agent(...)` itself — pulling in the orchestrator's prompt
   (§4) and the six fixed subagents (§5).
4. **`agent.invoke(...)` runs** — back in `run_pipeline` (§2), with
   `ProgressLogger` (§10) attached as a callback, driving both `logsink`
   and `run_events` for the entire run's duration, however many nested
   subagent calls it makes.
5. **The orchestrator follows its ten-step checklist** (§4) — delegating
   to discovery, then chunked extraction, then merge-planning, then
   batched/parallel resolution and drafting (§5), then QA with scoped
   retries, finally calling `write_output_workbook` (§7, the atomic-write
   tool) exactly once and writing `run_summary.json` itself via its
   built-in `write_file` tool (sandboxed to the run workspace by
   `FilesystemBackend`, §3).
6. **`run_pipeline` notices completion (or doesn't)** — the
   `summary_path.is_file()` check (§2) either ends the loop successfully or
   triggers an auto-continue nudge on the same conversation, up to
   `settings.MAX_AUTO_CONTINUE_TURNS` times.
7. **The result is reported back** — `run_pipeline` returns its dict (§2),
   which `sys5.py`/`main.py` (§1) reshape into their own respective public
   contracts.

For the "why is it built this way" reasoning behind any of the above — the
two-filesystems model, context management, run resilience, output-file
write safety, the full text of every subagent prompt, the skills/memory
layering diagram — see [`README.md`](./README.md), which this document is
a deliberate complement to, not a replacement for.
