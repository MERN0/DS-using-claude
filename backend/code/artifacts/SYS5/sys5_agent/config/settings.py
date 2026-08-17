"""
Single source of truth for every configurable value in the SYS2 -> SYS5 agent.

Nothing outside this file should hardcode a model name, path, threshold, or
column list. Override any value via the matching environment variable, or by
editing the defaults below.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

CLIENTS_DIR = REPO_ROOT / "clients"
DEFAULT_CLIENT_DIR_NAME = "_default"

RUNS_DIR = REPO_ROOT / "runs"
OUTPUT_DIR = REPO_ROOT / "output"

# Allowed shape for a client/project name or domain key once it's about to be
# joined onto CLIENTS_DIR/DOMAINS_DIR: letters, digits, '_', '-', '.' only.
# This is a hard backstop against path traversal (e.g. a project_name of
# "../../etc" from a calling backend) landing inside a Path join -- it is
# NOT primarily a UX validation, callers should still give a real name.
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def validate_safe_name(name: str, label: str) -> str:
    name = str(name).strip()
    if not name or not _SAFE_NAME_RE.match(name) or ".." in name:
        raise ValueError(
            f"Invalid {label} {name!r}: must contain only letters, digits, '_', '-', '.' (no path separators, no '..')."
        )
    return name


# ---------------------------------------------------------------------------
# Automotive domains
# ---------------------------------------------------------------------------

# A domain is passed once at the start of a run (--domain) and stays constant
# for the whole cycle. Each domain has a domains/<name>/skills/domain-knowledge/
# SKILL.md carrying the detailed items (ECUs/modules, signal/command naming
# conventions, buses, typical requirement/test patterns, terminology
# pitfalls) for that domain -- loaded on demand like any other skill, not
# preloaded into every turn's context.
DOMAINS_DIR = REPO_ROOT / "domains"

DOMAINS = ["bcm", "ivi", "ev", "powertrain", "adas", "chassis", "telematics"]

DOMAIN_LABELS = {
    "bcm": "Body Control Module",
    "ivi": "In-Vehicle Infotainment",
    "ev": "Electric Vehicle powertrain, battery & charging",
    "powertrain": "Powertrain (engine, transmission & driveline)",
    "adas": "Advanced Driver Assistance Systems",
    "chassis": "Chassis & vehicle dynamics (braking, steering, suspension)",
    "telematics": "Telematics & connectivity",
}

# Accepted alternate spellings/typos for --domain, normalized before lookup
# (e.g. the common misspelling of "chassis").
DOMAIN_ALIASES = {
    "chasis": "chassis",
}

# ---------------------------------------------------------------------------
# LLM endpoint (self-hosted Qwen, OpenAI-compatible)
# ---------------------------------------------------------------------------

LLM_MODEL = os.environ.get("SYS5_LLM_MODEL", "qwen-3.6-32b")
LLM_API_KEY = os.environ.get("SYS5_LLM_API_KEY", "not-needed")
LLM_BASE_URL = os.environ.get("SYS5_LLM_BASE_URL", "http://localhost:8000/v1")
LLM_TEMPERATURE = float(os.environ.get("SYS5_LLM_TEMPERATURE", "0.1"))

# Real total context window the endpoint in LLM_BASE_URL enforces. This is
# reported to the model as its `profile["max_input_tokens"]` (see
# agent/build.py) so deepagents' auto-attached SummarizationMiddleware
# compacts the conversation at 85% of it -- a self-hosted, OpenAI-compatible
# model name like the LLM_MODEL default has no entry in langchain_openai's
# built-in profile registry, so without this value the middleware falls
# back to a fixed 170k-token trigger regardless of what the endpoint
# actually enforces, which is exactly how a long run (many requirements,
# many clusters) used to end in a hard "exceeds maximum context length"
# rejection from the server instead of ever compacting. Set this to
# whatever LLM_BASE_URL's model card/server config actually advertises --
# UNDER-reporting it here just triggers compaction earlier than strictly
# necessary (cheap); OVER-reporting it reintroduces this same failure.
LLM_CONTEXT_TOKENS = int(os.environ.get("SYS5_LLM_CONTEXT_TOKENS", "100000"))

# The orchestrator's own agent loop ends the instant its latest message has
# no tool call in it -- which normally only happens once run_summary.json
# has actually been written, but a model can also just stop early (e.g.
# emit a chatty "here's my status so far" reply instead of continuing to
# delegate) with nothing forcing it to keep going. `run_pipeline` treats
# "no run_summary.json yet" as "not actually done" and re-invokes the same
# thread (see agent/build.py's checkpointer) with a short nudge to continue,
# up to this many times, before giving up and reporting the run as
# genuinely incomplete rather than looping forever against a model that's
# stuck.
MAX_AUTO_CONTINUE_TURNS = int(os.environ.get("SYS5_MAX_AUTO_CONTINUE_TURNS", "8"))

# ---------------------------------------------------------------------------
# Chunking / merge / retry knobs
# ---------------------------------------------------------------------------

# How many requirement rows the requirement-extraction subagent reads per
# task() call. Kept conservative to leave headroom for tool schemas, the
# loaded skill, and memory inside one subagent turn.
REQUIREMENT_CHUNK_SIZE = int(os.environ.get("SYS5_REQUIREMENT_CHUNK_SIZE", "40"))

# Hard cap on how many requirements the merge-planning agent may collapse
# into a single test case, to prevent runaway/unwieldy merges.
MAX_REQS_PER_TESTCASE = int(os.environ.get("SYS5_MAX_REQS_PER_TESTCASE", "6"))

# Upper bound on how many independent clusters resolution-agent /
# test-case-drafting-agent may be asked to handle in one task() call --
# processed independently within that call (never blended), one
# resolved/<cluster_id>.md or draft row per cluster either way. This exists
# purely to cut down on the number of separate LLM-backed delegations for a
# run with many small clusters; it is not a correctness knob.
MAX_CLUSTER_BATCH_SIZE = int(os.environ.get("SYS5_MAX_CLUSTER_BATCH_SIZE", "3"))

# Bounded retries for the resolution subagent's search loop per cluster
# before an item is marked `unresolved` instead of guessed.
MAX_RESOLUTION_ATTEMPTS = int(os.environ.get("SYS5_MAX_RESOLUTION_ATTEMPTS", "5"))

# Bounded retries for the QA feedback loop (re-draft / re-resolve flagged
# clusters) before the run proceeds with recorded warnings.
MAX_QA_RETRIES = int(os.environ.get("SYS5_MAX_QA_RETRIES", "2"))

# Bounded retries specifically for a *critical*-priority test case that is
# still failing QA after the general retry budget above. Critical items get
# this extra, separately-tracked budget because silently shipping a broken
# critical test case is worse than spending more retries on it; once this is
# also exhausted the item is marked incomplete/failed rather than retried
# forever (see ORCHESTRATOR_SYSTEM_PROMPT).
CRITICAL_MAX_RETRIES = int(os.environ.get("SYS5_CRITICAL_MAX_RETRIES", "3"))

# Rows previewed when classifying an unknown sheet during discovery.
SHEET_PREVIEW_ROWS = int(os.environ.get("SYS5_SHEET_PREVIEW_ROWS", "5"))

# Row-range size returned by a single read_sheet_range call (independent of
# REQUIREMENT_CHUNK_SIZE so other sheet types can use a different size).
MAX_ROWS_PER_READ = int(os.environ.get("SYS5_MAX_ROWS_PER_READ", "200"))

# Row cap on a single search_sheet call's returned matches.
MAX_SEARCH_RESULTS = int(os.environ.get("SYS5_MAX_SEARCH_RESULTS", "50"))

# ---------------------------------------------------------------------------
# Requirement qualification markers
# ---------------------------------------------------------------------------

# Case-insensitive substrings that mark a requirement row as needing a SYS5
# test case. Checked against any cell in the row, not a fixed column, since
# clients place this marker differently (dedicated column, inline text,
# footnote). Extend per-client via clients/<name>/memory/AGENTS.md if a
# client uses a marker not covered here -- the agent is told to treat this
# list as a starting point, not an exhaustive one.
QUALIFICATION_MARKERS = [
    "sys qualification test",
    "sys5 test",
    "system qualification test",
]

# ---------------------------------------------------------------------------
# Check type classification
# ---------------------------------------------------------------------------

# The fixed set of check types a test case can perform. Every qualifying
# requirement is classified against these (one or more, per its description)
# during extraction; a requirement needing more than one check type produces
# one test case per applicable type -- see the merging-strategy skill.
CHECK_TYPES = [
    "Boundary Value Check",
    "Invalid Values Check",
    "Functionality Check",
    "Stress Test",
    "Load Test",
]

# ---------------------------------------------------------------------------
# Output contract -- the fixed 13-column SYS5 template
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = [
    "Test Case ID",
    "Feature/Module",
    "Variant",
    "Check Type",
    "Traceability",
    "Test Case Objective",
    "Test Case Description",
    "Test Precondition",
    "Test Input Data",
    "Test Steps",
    "Expected Result",
    "Mode of Execution",
    "Priority",
]

OUTPUT_SHEET_NAME = "SYS5_Test_Cases"

# Output file formats the write tool actually knows how to produce. Kept as
# an explicit whitelist (rather than accepting any extension a caller passes)
# since only xlsx is implemented today.
SUPPORTED_OUTPUT_FORMATS = ["xlsx"]

# Fixed Test Case ID format: f"{TEST_CASE_ID_PREFIX}{n}" for n = 1, 2, 3...
# in final output row order. write_output_workbook (tools/excel_tools.py)
# assigns this itself, unconditionally overwriting whatever the drafting
# agent put in that column -- that's deliberate, not a bug: it's the one
# point in the pipeline that can actually guarantee both the fixed format
# and uniqueness across the whole file in one place, rather than relying on
# every drafting call (each running in its own isolated cluster, possibly
# in parallel with others) to independently avoid colliding with IDs it has
# no visibility into. Nothing else in the pipeline keys off Test Case ID
# (Traceability tracks requirement IDs, resolution/QA key off cluster_id),
# so overwriting it here has no downstream effect to account for.
TEST_CASE_ID_PREFIX = "TC_SYS_"

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

DEBUG = os.environ.get("SYS5_DEBUG", "0") == "1"


def client_dir(client: str) -> Path:
    """Resolve a client/project name to its clients/<name> directory, falling
    back to the client's own dir even if it doesn't exist yet (caller decides
    how to handle a missing client). Raises ValueError if `client` isn't a
    safe path segment (see validate_safe_name)."""
    return CLIENTS_DIR / validate_safe_name(client, "client/project name")


def default_client_dir() -> Path:
    return CLIENTS_DIR / DEFAULT_CLIENT_DIR_NAME


def normalize_domain(domain: str) -> str:
    """Lowercase/trim a --domain value and resolve known aliases/typos
    (e.g. "chasis" -> "chassis") to the canonical domain key."""
    key = domain.strip().lower()
    return DOMAIN_ALIASES.get(key, key)


def domain_dir(domain: str) -> Path:
    """Resolve a domain name to its domains/<name> directory, falling back
    to the domain's own dir even if it doesn't exist yet (caller decides how
    to handle an unknown domain). Raises ValueError if `domain` isn't a safe
    path segment (see validate_safe_name) -- this does NOT check `domain`
    is one of the recognized DOMAINS; callers should validate that
    separately (e.g. `normalize_domain(domain) in DOMAINS`) when they need a
    hard "unsupported domain" error rather than just a missing directory."""
    return DOMAINS_DIR / validate_safe_name(normalize_domain(domain), "domain")
