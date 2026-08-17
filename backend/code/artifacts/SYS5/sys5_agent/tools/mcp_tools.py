"""
Optional, curated MCP (Model Context Protocol) tools -- off by default (see
`config.settings.MCP_ENABLED`), for a client's custom subagents to opt into
through the same "Tools it can use" checkbox mechanism they already use for
the 5 sandboxed Excel tools (see `agent/custom_subagents.py` and
`frontend/builders.py`'s `available_tools()`).

This is a fixed, code-reviewed allowlist, not a place a client (or the UI)
ever supplies its own MCP server command/URL: unlike every other tool in
this codebase, an MCP server has no path/directory sandboxing at all -- it
gets whatever filesystem/network/API scope its own process declares. Vetting
happens here, once, by whoever edits `MCP_SERVERS`, not per-client.

## The two servers

- `fetch` (official reference `mcp-server-fetch`, launched via `uvx`):
  read-only URL fetch, converted to readable text/markdown. Useful for
  looking up automotive standards/terminology a client's requirements
  reference. No filesystem access.
- `sequential-thinking` (official reference `@modelcontextprotocol/
  server-sequential-thinking`, launched via `npx`): a structured multi-step
  reasoning scratchpad tool. No filesystem or network access at all -- the
  safest possible server, useful for an unusually ambiguous
  resolution/merge-planning call.

Neither built-in subagent nor the orchestrator gets these -- only
client-authored custom subagents can opt in, so the always-on core
pipeline's latency/surface is unaffected whether or not `MCP_ENABLED` is
set. Fetching tools from a cold `npx`/`uvx` process can take a while (a
first-run package resolution measured well over a minute in testing) --
see `settings.MCP_TOOL_TIMEOUT_SECONDS`.

## Failure handling

Every server is tried independently, with its own timeout; a server that
fails to start (missing Node/uv, network hiccup fetching the package,
timeout) is logged and skipped -- it never fails a whole run, mirroring
`agent/custom_subagents.py`'s "one bad thing never fails a whole run"
philosophy. `MCP_ENABLED=false` (the default) skips all of this entirely,
with zero import-time cost -- `langchain_mcp_adapters`/`mcp` are only
imported inside the function below, not at module load time, so this
module is safe to import even in an environment that never installed
those optional dependencies.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sys5_agent.config import settings

# Fixed, code-reviewed server definitions -- see the module docstring.
# `mcp<2.0.0` is pinned on the `fetch` server's own command line (not just
# in requirements.txt) because `uvx` resolves its own isolated environment
# per invocation, independent of whatever's pip-installed for this process
# -- see requirements.txt's comment on why mcp>=2.0.0 doesn't work at all
# with the current MCP ecosystem.
MCP_SERVERS: dict[str, dict[str, Any]] = {
    "fetch": {
        "transport": "stdio",
        "command": "uvx",
        "args": ["--with", "mcp>=1.24.0,<2.0.0", "mcp-server-fetch"],
    },
    "sequential-thinking": {
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
    },
}


async def _fetch_mcp_tools_async() -> list:
    """Try every server in MCP_SERVERS independently; a failure on one
    (missing binary, network issue, timeout) is logged and skipped rather
    than raised, same tolerance `custom_subagents.py` applies to a bad
    client-authored subagent file."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(MCP_SERVERS)
    tools: list = []
    for name in MCP_SERVERS:
        try:
            server_tools = await asyncio.wait_for(
                client.get_tools(server_name=name), timeout=settings.MCP_TOOL_TIMEOUT_SECONDS
            )
        except Exception as e:  # noqa: BLE001 -- an optional server failing must never fail a run
            print(f"[mcp-tools] '{name}' unavailable, skipping: {type(e).__name__}: {e}", flush=True)
            continue
        tools.extend(server_tools)
        print(f"[mcp-tools] loaded {len(server_tools)} tool(s) from '{name}'", flush=True)
    return tools


def fetch_mcp_tools() -> list:
    """Synchronous entry point for `agent/build.py` -- fetches tools from
    every server in MCP_SERVERS once (not once per subagent, to avoid
    launching redundant server subprocesses within a single run). Returns
    [] immediately, without attempting anything, if `MCP_ENABLED` is off.

    Safe to call from `build_agent()`'s synchronous code specifically
    because that function is never itself called from inside an already-
    running event loop in this codebase today (the CLI's `main()` and
    `frontend/app.py`'s background `threading.Thread` both start with no
    active loop) -- `asyncio.run()` raises if that assumption ever stops
    holding, which is the right failure mode (loud, not a silent hang).
    """
    if not settings.MCP_ENABLED:
        return []
    try:
        return asyncio.run(_fetch_mcp_tools_async())
    except Exception as e:  # noqa: BLE001 -- MCP tooling is optional; never fail a run over it
        print(f"[mcp-tools] failed to fetch MCP tools, continuing without them: {type(e).__name__}: {e}", flush=True)
        return []


def available_mcp_tool_names() -> dict[str, str]:
    """{tool_name: one-line description} for the UI's "Tools it can use"
    checkbox list (see frontend/builders.py's available_tools()) -- always
    returns the full curated set regardless of MCP_ENABLED, so a client can
    see and select these tools even before an operator turns the feature
    on; the run itself simply won't have them available until it is."""
    return {
        "fetch": "Fetch a URL from the internet and read its contents (e.g. a terminology/standards page).",
        "sequentialthinking": "A structured scratchpad for multi-step reasoning -- no filesystem or network access.",
    }
