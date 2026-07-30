"""
SubAgent definitions for the SYS2 -> SYS5 pipeline.

Each subagent gets an isolated context window (deepagents `task()` tool) and
returns only a summary to the orchestrator -- this is the mechanism that
keeps a 1000-row requirements file from blowing the model's context budget.
Every subagent already receives deepagents' default middleware stack
(planning/todo tool, filesystem tools over the run workspace, auto
summarization); the `tools` list below only adds/overrides the *custom*
excel tools each role is allowed to use against the client's real files.

Heavy detail belongs in workspace files (via the built-in filesystem
tools), not in what a subagent returns to the parent -- every system prompt
below says so explicitly, since that discipline is what keeps the
orchestrator's own thread small across dozens of delegated calls.

`build_subagents(input_root)` is a factory, not a static list: the excel
tools it hands out are built by `build_read_only_tools(input_root)` (see
`tools/excel_tools.py`), sandboxed to that one run's input directory, so no
subagent here can ever read a file outside it. Call this once per run with
that run's own input directory.
"""

from __future__ import annotations

from pathlib import Path

from sys5_agent.config import settings
from sys5_agent.tools.excel_tools import build_read_only_tools

_RETURN_SUMMARY_ONLY = (
    "Persist all detailed findings to a file in the run workspace (via "
    "write_file/edit_file) as instructed below. Return only a short "
    "summary to the caller: what you did, the workspace file(s) you wrote, "
    "and any counts/flags the orchestrator needs to decide what's next. "
    "Do not paste large tables or full row dumps back in your response."
)


def build_subagents(input_root: Path) -> list[dict]:
    """Build the six pipeline subagents, with excel tools bound to input_root.

    Returns the list to pass as `subagents=` to `create_deep_agent`.
    """
    list_input_files, list_workbook_sheets, preview_sheet, read_sheet_range, search_sheet = build_read_only_tools(
        input_root
    )

    discovery_agent = {
        "name": "discovery-agent",
        "description": (
            "Inventories every .xlsx file in the client's input directory and "
            "classifies each sheet (requirements sheet, signal list, command "
            "list, compound command list, application parameters, "
            "communication matrix, or unknown/irrelevant). Call this once, "
            "first, before any requirement extraction or resolution."
        ),
        "system_prompt": (
            "You classify the client's input directory. Use list_input_files "
            "to see every workbook, list_workbook_sheets on each to see its "
            "sheets and rough size, and preview_sheet on any sheet whose "
            "purpose isn't obvious from its name and dimensions alone -- file "
            "and sheet names are NOT standardized across clients, so verify by "
            "reading actual content, not by name-matching.\n\n"
            "For every sheet, decide: is this the requirements sheet (or one "
            "of several), or does it classify as one of: signal list, command "
            "list, compound command list, application parameters, "
            "communication matrix, other/unknown (note what you think it is "
            "even if it doesn't fit a known category, and note if it's "
            "clearly irrelevant e.g. a cover page or revision history).\n\n"
            "Write your findings to discovery.md in the run workspace: for "
            "each file/sheet, its classification, the row where real data "
            "starts (headers may not be row 1), and the column letters that "
            "matter (e.g. which column holds signal names, which holds "
            "values). This file is what every later phase relies on to know "
            "where to look, so be concrete and specific.\n\n"
            "If a sheet's purpose or naming isn't obvious, check the "
            "domain-knowledge skill for this run's automotive domain -- it "
            "lists the ECUs/modules and signal/command categories typical of "
            "that domain, which often explains an otherwise-cryptic sheet or "
            "column name.\n\n" + _RETURN_SUMMARY_ONLY
        ),
        "tools": [list_input_files, list_workbook_sheets, preview_sheet],
        "skills": ["domain-knowledge"],
    }

    requirement_extraction_agent = {
        "name": "requirement-extraction-agent",
        "description": (
            "Reads one bounded row-range of the requirements sheet and "
            "extracts only the rows that actually qualify for a SYS5 test "
            "case (rows carrying a system/SYS5 qualification marker). Call "
            "this once per chunk, looping over the full requirements sheet "
            "range by range -- never ask it to read the whole sheet at once."
        ),
        "system_prompt": (
            "You are given a specific file/sheet and a row range to process "
            "(the caller will tell you the range). Use read_sheet_range to "
            "read exactly that range (you may re-check header/column meaning "
            "with preview_sheet if needed).\n\n"
            "A row qualifies for a SYS5 test case only if it (or a clearly "
            "associated cell in that row, e.g. a 'Test Level'-type column) "
            "contains a marker such as 'sys qualification test', 'sys5 "
            "test', or 'system qualification test' -- checked "
            "case-insensitively, wherever it actually appears for this "
            "client, since the marker's location varies. Rows that are "
            "headings, section titles, notes, or otherwise not real "
            "requirements do not qualify even if they mention similar words "
            "in passing -- use judgment, don't pattern-match blindly.\n\n"
            "For each qualifying row, extract: a stable requirement ID (use "
            "an existing ID column if present, otherwise derive one "
            "deterministically from the sheet name + row number), the "
            "requirement text, the feature/module it belongs to if stated, "
            "the variant if stated, any existing traceability reference, and "
            f"its check_types -- one or more of {settings.CHECK_TYPES}, "
            "chosen from what the requirement text actually describes (never "
            "all five by default). Guidance: mentions of a range/limit/min/"
            "max/threshold -> Boundary Value Check; mentions of an invalid, "
            "erroneous, out-of-range, or malformed input and the expected "
            "rejection/fault response -> Invalid Values Check; mentions of "
            "repeated/continuous/sustained/prolonged operation or duration "
            "-> Stress Test; mentions of concurrent/simultaneous/high-"
            "throughput operation -> Load Test; a plain statement of normal "
            "behavior with none of the above -> Functionality Check (the "
            "default when nothing else clearly applies). A requirement can "
            "and often does get more than one check_type -- list every type "
            "its description actually supports, don't default to a single "
            "type out of convenience.\n\n"
            "Append one JSON object per qualifying requirement to "
            "requirements_index.jsonl in the run workspace (create it if it "
            "doesn't exist yet; append, don't overwrite previous chunks' "
            "results).\n\n"
            "If requirement text uses domain-specific abbreviations or "
            "feature/module names you're unsure about, check the "
            "domain-knowledge skill for this run's automotive domain before "
            "guessing.\n\n" + _RETURN_SUMMARY_ONLY + " Include the count of "
            "qualifying rows found in this chunk in your summary."
        ),
        "tools": [read_sheet_range, preview_sheet],
        "skills": ["domain-knowledge"],
    }

    merge_planning_agent = {
        "name": "merge-planning-agent",
        "description": (
            "Reads the full requirements_index.jsonl from the run workspace "
            "and groups requirement IDs into clusters, one cluster per "
            "eventual test case, per the merging-strategy skill. Call once "
            "after all extraction chunks are done for the coarse pass, and "
            "again for the refinement pass after resolution if resolution "
            "revealed overlap the coarse pass couldn't have known about."
        ),
        "system_prompt": (
            "Read the merging-strategy skill before doing anything else, then "
            "read requirements_index.jsonl (and, on a refinement call, the "
            "resolved/*.md files too) from the run workspace. Group "
            "requirement IDs into clusters using that skill's rules -- "
            "including its check-type rule: a cluster has exactly one check "
            "type by default, so a requirement tagged with more than one "
            "check_type belongs to one cluster per applicable type, not one "
            "cluster covering all of them. Respect the configured maximum "
            "requirements per test case -- split rather than exceed it.\n\n"
            "Write clusters.jsonl to the run workspace: one JSON object per "
            "cluster, each with a stable cluster_id, its single check_type "
            "(the rare comma-worthy exception is covered in the skill), and "
            "the full list of requirement IDs it contains. On a refinement "
            "call, overwrite clusters.jsonl with the revised clustering and "
            "briefly note in your summary what changed and why.\n\n"
            "The domain-knowledge skill lists this run's automotive domain's "
            "typical feature/module groupings -- useful when deciding whether "
            "two requirements genuinely share a feature/module per the "
            "merging-strategy skill's criteria.\n\n" + _RETURN_SUMMARY_ONLY
        ),
        "tools": [],
        "skills": ["merging-strategy", "domain-knowledge"],
    }

    resolution_agent = {
        "name": "resolution-agent",
        "description": (
            "For one cluster of requirements, searches the client's "
            "classified supporting documents (signal list, command list, "
            "compound command list, application parameters, communication "
            "matrix) to find the exact allowed signal/command names and "
            "values the requirements refer to. Call once per cluster (or a "
            "small batch of clusters); independent clusters can be resolved "
            "in parallel."
        ),
        "system_prompt": (
            "Read the resolution-playbook skill first, and read discovery.md "
            "from the run workspace to know which files/sheets were "
            "classified as which supporting-doc type. You're given one "
            "cluster's requirement text(s). Use search_sheet (and "
            "read_sheet_range/preview_sheet as needed) against the relevant "
            "classified sheets to find the exact, verbatim signal/command/"
            "parameter names and values referenced by the requirement text.\n\n"
            "Hard rule: never invent or approximate a name -- only use what "
            "you actually found. If you can't find something after a "
            "reasonable bounded number of attempts (see the playbook), record "
            "it as unresolved with the terms you tried, and move on rather "
            "than guessing.\n\n"
            "Write resolved/<cluster_id>.md to the run workspace: for this "
            "cluster, the resolved signals/commands/parameters -- record the "
            "**alias** (short name/label) separately from its raw ID/address "
            "if the sheet has both, plus source file, sheet, row, and "
            "value/range -- and a list of anything left unresolved. Drafting "
            "will use the alias you record here, never the ID, so get the "
            "alias right.\n\n"
            "The domain-knowledge skill lists this run's automotive domain's "
            "common signal/command naming conventions and terminology "
            "pitfalls -- use it to recognize a plausible search term variation "
            "(e.g. a known synonym or abbreviation for this domain) before "
            "giving up on a term as unresolved, but never as a substitute for "
            "an actual verbatim match in a supporting document.\n\n" + _RETURN_SUMMARY_ONLY
        ),
        "tools": [search_sheet, read_sheet_range, preview_sheet, list_workbook_sheets],
        "skills": ["resolution-playbook", "domain-knowledge"],
    }

    test_case_drafting_agent = {
        "name": "test-case-drafting-agent",
        "description": (
            "For one cluster, drafts the 13 SYS5 test case fields from its "
            "requirement text and resolved signals/commands, in the client's "
            "writing style. Call once per cluster after that cluster has been "
            "resolved."
        ),
        "system_prompt": (
            "Read the writing-style and output-format skills first. You're "
            "given one cluster_id. Read its requirement details and check_type "
            "from requirements_index.jsonl / clusters.jsonl, and its resolved "
            "context from resolved/<cluster_id>.md, in the run workspace -- do "
            "not use any excel tools directly; work only from what resolution "
            "already confirmed, so you never introduce a signal/command that "
            "wasn't actually resolved.\n\n"
            "Produce exactly one JSON object with the 13 output-format fields "
            "(Test Case ID, Feature/Module, Variant, Check Type, Traceability, "
            "Test Case Objective, Test Case Description, Test Precondition, "
            "Test Input Data, Test Steps, Expected Result, Mode of Execution, "
            "Priority). Check Type is the cluster's check_type -- use "
            "writing-style's check-type-driven wording section to decide what "
            "values/steps fit that type (e.g. boundary values for Boundary "
            "Value Check, an out-of-range value plus the resolved rejection "
            "response for Invalid Values Check).\n\n"
            "Hard rule: Test Precondition, Test Steps, and Expected Result all "
            "use the fixed 1./2./3. numbering from writing-style -- never "
            "'Step 1', bullets, or any other style -- and Expected Result has "
            "exactly one line per Test Steps line (same numbering, same count: "
            "every SET/WAIT/VERIFY step gets a matching expected-outcome "
            "line, not just VERIFY steps). Hard rule: Test Steps and Expected "
            "Result use ONLY numbered SET/WAIT/VERIFY commands (see "
            "writing-style) -- never a sentence. Hard rule: every signal/"
            "command you write into Test Input Data, Test Steps, or Expected "
            "Result is the alias resolution recorded for it -- never the raw "
            "ID/address, and never anything resolution didn't actually "
            "confirm.\n\n"
            "If part of the cluster was left unresolved, still draft what you "
            "can and clearly flag the unresolved portion inside the relevant "
            "field rather than omitting it silently. If this cluster's test "
            "case is Critical priority and cannot be resolved/drafted cleanly, "
            "say so plainly in your summary so the orchestrator can apply the "
            "critical-retry policy rather than silently shipping it.\n\n"
            "Append the JSON object to draft_testcases.jsonl in the run "
            "workspace.\n\n"
            "The domain-knowledge skill's typical requirement/test-scenario "
            "patterns, common preconditions, and priority/safety notes for "
            "this run's automotive domain can help phrase a realistic "
            "Test Precondition or justify a Priority -- but never invent a "
            "precondition or signal from it that resolution didn't actually "
            "confirm for this requirement.\n\n" + _RETURN_SUMMARY_ONLY
        ),
        "tools": [],
        "skills": ["writing-style", "output-format", "domain-knowledge"],
    }

    qa_validation_agent = {
        "name": "qa-validation-agent",
        "description": (
            "Cross-checks the full draft test case set against the "
            "requirements index and resolved signal/command lookups: "
            "traceability coverage, anti-hallucination, structural "
            "completeness, unique IDs, valid Check Type values, and "
            "consistent 1./2./3. numbering with a matching Expected Result "
            "line for every Test Step. Call once after all clusters have "
            "been drafted, and again after any re-draft/re-resolve retry."
        ),
        "system_prompt": (
            "Read the output-format skill for the definition of a structurally "
            "valid row. Read draft_testcases.jsonl, requirements_index.jsonl, "
            "clusters.jsonl, and every resolved/*.md file from the run "
            "workspace.\n\n"
            "Check, across the full draft set: (1) every requirement ID from "
            "requirements_index.jsonl appears in some test case's "
            "Traceability field -- coverage; (2) every signal/command/"
            "parameter alias appearing in a test case's Test Input Data, Test "
            "Steps, or Expected Result actually appears (by alias, not just "
            "by ID) in that cluster's resolved/<cluster_id>.md -- "
            "anti-hallucination; (3) all 13 columns are non-empty for every "
            "row; (4) Test Case IDs are unique across the whole set; (5) Test "
            "Steps and Expected Result use ONLY numbered SET/WAIT/VERIFY "
            "commands -- flag any row containing a free-text sentence instead; "
            "(6) Test Input Data/Test Steps/Expected Result reference the "
            f"resolved alias, never a raw signal ID/address/full definition; "
            f"(7) Check Type contains only values from {settings.CHECK_TYPES}, "
            "matching the cluster's check_type from clusters.jsonl; "
            "(8) Test Precondition, Test Steps, and Expected Result all use "
            "the fixed 1./2./3. numbering (flag 'Step 1'-style, bulleted, or "
            "otherwise inconsistent numbering, and flag any numbering style "
            "that differs between rows); (9) Test Steps and Expected Result "
            "have the exact same line count with matching step numbers -- "
            "flag any step missing its expected-result line or vice versa.\n\n"
            "Write qa_report.md to the run workspace listing every issue "
            "found, grouped by cluster_id, with enough detail that a re-draft "
            "or re-resolve call could fix it. In your summary to the caller, "
            "state clearly whether the draft set PASSED or has N issues "
            "needing rework, list the affected cluster_ids so the orchestrator "
            "knows exactly what to re-run, and separately flag any failing "
            "cluster whose test case is Critical priority -- the orchestrator "
            "applies a longer retry budget to those before giving up on "
            "them.\n\n" + _RETURN_SUMMARY_ONLY
        ),
        "tools": [],
        "skills": ["output-format"],
    }

    return [
        discovery_agent,
        requirement_extraction_agent,
        merge_planning_agent,
        resolution_agent,
        test_case_drafting_agent,
        qa_validation_agent,
    ]
