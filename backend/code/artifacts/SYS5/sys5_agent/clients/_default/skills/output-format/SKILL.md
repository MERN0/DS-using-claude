---
name: output-format
description: The canonical definition of the 13 fixed SYS5 output columns (including Check Type) and what a complete, valid value looks like for each. Use during drafting and QA validation to check a test case is structurally complete before it's written to the output workbook.
---

# Output Format Contract

Every test case is exactly one row with these 13 columns, in this exact
order. Column names are fixed — do not rename, reorder, add, or remove.

1. **Test Case ID** — fixed format `TC_SYS_<n>` (e.g. `TC_SYS_1`,
   `TC_SYS_2`, ...), assigned automatically by `write_output_workbook` in
   final row order -- it overwrites whatever is passed in this column, so
   don't spend effort inventing one during drafting or worry about
   colliding with another cluster's numbering; any placeholder here is
   fine. Nothing else in the pipeline keys off this value (Traceability
   uses requirement IDs; resolution/QA key off `cluster_id`), so this is
   the only column drafting truly cannot get wrong.
2. **Feature/Module** — the feature or module this test case belongs to,
   taken from the requirement's tagging/section in the source document.
3. **Variant** — product/vehicle variant this test case applies to, if the
   source distinguishes variants; otherwise `All` / `N/A` as appropriate
   for this client (check client override).
4. **Check Type** — one or more of the fixed check types (see
   `CHECK_TYPES` in config): `Boundary Value Check`, `Invalid Values
   Check`, `Functionality Check`, `Stress Test`, `Load Test`. Comma-
   separated only in the rare case a single test case genuinely can't be
   split (see `merging-strategy`); normally one test case targets exactly
   one check type, and a requirement needing several types produces one
   test case per type. Never blank, and never a value outside this fixed
   list.
5. **Traceability** — every source requirement ID covered by this test
   case, comma-separated if merged. Never blank for a generated test case.
6. **Test Case Objective** — one sentence, why this test exists.
7. **Test Case Description** — short paragraph, what scenario is exercised.
8. **Test Precondition** — numbered list (`1.`, `2.`, `3.`, ... — see
   `writing-style`'s fixed numbering scheme) of system state required
   before execution, one clause per line.
9. **Test Input Data** — resolved alias(es) and exact values to apply —
   alias + parameters only (see below), not a raw ID or description.
10. **Test Steps** — numbered `SET`/`WAIT`/`VERIFY` commands only, one per
    step, using the fixed `1.`/`2.`/`3.` numbering; see `writing-style` for
    the exact syntax. Never a sentence.
11. **Expected Result** — one line per Test Steps line, same numbering and
    step count, describing that step's expected outcome; see
    `writing-style`. Never a sentence, never fewer lines than Test Steps.
12. **Mode of Execution** — how the test is run (e.g. `Manual`,
    `Automated`/bench, as applicable).
13. **Priority** — severity/priority as given or reasonably inferred (see
    `writing-style` skill for the fallback rule).

## Alias-only rule (anti-hallucination, applies to columns 9-11)

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
  DoorLockCmd = LOCK`, not a dump of the command's full row/definition.

## Definition of "complete" for QA purposes

A row is structurally valid when: all 13 columns are non-empty (Test Case
ID is assigned automatically at write time -- see above -- so it's never
actually missing or a duplicate by the time this matters), Check Type
contains only values from the fixed `CHECK_TYPES` list, Traceability lists
only requirement IDs that were actually extracted as qualifying in this
run, Test Precondition/Test Steps/Expected Result all use the fixed
`1.`/`2.`/`3.` numbering (never `Step 1`, bullets, or any other style —
see `writing-style`), Test Steps and Expected Result have the exact same
number of lines with matching step numbers (every step has a corresponding
expected-result line and vice versa), Test Steps/Expected Result use only
the `SET`/`WAIT`/`VERIFY` syntax with the fixed `=` (assignment) /
`==` (comparison) operators -- no free-text sentences, no comma or word
standing in for either operator -- and every alias named in Test Input
Data/Test Steps/Expected Result was confirmed during resolution by alias
(not invented, not a raw ID). A row failing any of these checks should be
flagged by QA, not written to the final output as-is.

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
