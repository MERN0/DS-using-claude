---
name: output-format
description: The canonical definition of the 12 fixed SYS5 output columns and what a complete, valid value looks like for each. Use during drafting and QA validation to check a test case is structurally complete before it's written to the output workbook.
---

# Output Format Contract

Every test case is exactly one row with these 12 columns, in this exact
order. Column names are fixed — do not rename, reorder, add, or remove.

1. **Test Case ID** — unique, stable identifier for this test case (e.g.
   `TC_<feature>_<sequence>`). Must be unique across the whole output file.
2. **Feature/Module** — the feature or module this test case belongs to,
   taken from the requirement's tagging/section in the source document.
3. **Variant** — product/vehicle variant this test case applies to, if the
   source distinguishes variants; otherwise `All` / `N/A` as appropriate
   for this client (check client override).
4. **Traceability** — every source requirement ID covered by this test
   case, comma-separated if merged. Never blank for a generated test case.
5. **Test Case Objective** — one sentence, why this test exists.
6. **Test Case Description** — short paragraph, what scenario is exercised.
7. **Test Precondition** — system state required before execution.
8. **Test Input Data** — resolved alias(es) and exact values to apply —
   alias + parameters only (see below), not a raw ID or description.
9. **Test Steps** — numbered `SET`/`WAIT`/`VERIFY` commands only, one per
   step; see `writing-style` for the exact syntax. Never a sentence.
10. **Expected Result** — the corresponding `VERIFY` line(s) restated with
    expected parameters; see `writing-style`. Never a sentence.
11. **Mode of Execution** — how the test is run (e.g. `Manual`,
    `Automated`/bench, as applicable).
12. **Priority** — severity/priority as given or reasonably inferred (see
    `writing-style` skill for the fallback rule).

## Alias-only rule (anti-hallucination, applies to columns 8-10)

Every signal/command referenced in Test Input Data, Test Steps, or Expected
Result must be:

- **Verbatim-resolved** — found by the resolution phase in an actual
  supporting document, never guessed or approximated.
- **Named by alias, not by ID** — use the short alias/name a signal or
  command is known by (its "Name"/"Alias"-type column), never its raw
  message ID, address, or full technical definition. If resolution recorded
  both, the alias is what goes in the test case; the ID is reference-only
  and stays in `resolved/<cluster_id>.md`, not in the output row.
- **Given with its parameters, not the whole entry** — e.g. `SET
  DoorLockCmd, LOCK`, not a dump of the command's full row/definition.

## Definition of "complete" for QA purposes

A row is structurally valid when: all 12 columns are non-empty, Test Case
ID is unique in the file, Traceability lists only requirement IDs that were
actually extracted as qualifying in this run, Test Steps/Expected Result
use only the `SET`/`WAIT`/`VERIFY` syntax (no free-text sentences), and
every alias named in Test Input Data / Test Steps / Expected Result was
confirmed during resolution by alias (not invented, not a raw ID). A row
failing any of these checks should be flagged by QA, not written to the
final output as-is.

## Incomplete / failed critical test cases

If a `Critical`-priority test case still fails QA after the bounded retry
budget (general `MAX_QA_RETRIES`, then the extra `CRITICAL_MAX_RETRIES` for
critical items specifically — see the orchestrator's rules), it is still
written to the output rather than silently dropped, marked in-place so a
reviewer sees it immediately:

- Prefix **Test Case Objective** with `[INCOMPLETE]` or `[FAILED]` as
  appropriate.
- State the concrete reason (what couldn't be resolved/validated, and
  what was tried) at the end of **Test Case Description**.
- Keep **Traceability** intact — the requirement IDs still map here even
  though the test case itself is incomplete; do not drop coverage.
- Also list the item (cluster_id, requirement IDs, reason) under a
  `critical_failures` entry in `run_summary.json`.
