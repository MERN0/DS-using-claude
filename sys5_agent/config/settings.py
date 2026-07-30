"""
Single source of truth for every configurable value in the SYS2 -> SYS5 agent.

Nothing outside this file should hardcode a model name, path, threshold, or
column list. Override any value via the matching environment variable, or by
editing the defaults below.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

CLIENTS_DIR = REPO_ROOT / "clients"
DEFAULT_CLIENT_DIR_NAME = "_default"

RUNS_DIR = REPO_ROOT / "runs"
OUTPUT_DIR = REPO_ROOT / "output"

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

# Total context window advertised by the hosted model. Used only to size
# chunking/budget heuristics below -- never assume more than this is safe.
LLM_CONTEXT_TOKENS = int(os.environ.get("SYS5_LLM_CONTEXT_TOKENS", "130000"))

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
# Output contract -- the fixed 12-column SYS5 template
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS = [
    "Test Case ID",
    "Feature/Module",
    "Variant",
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

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

DEBUG = os.environ.get("SYS5_DEBUG", "0") == "1"


def client_dir(client: str) -> Path:
    """Resolve a client name to its clients/<name> directory, falling back
    to the client's own dir even if it doesn't exist yet (caller decides how
    to handle a missing client)."""
    return CLIENTS_DIR / client


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
    to handle an unknown domain)."""
    return DOMAINS_DIR / normalize_domain(domain)
