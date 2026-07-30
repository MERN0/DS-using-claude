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
8. **Test Input Data** — exact resolved signal/command names and values to
   apply.
9. **Test Steps** — numbered, imperative, one action per step.
10. **Expected Result** — precise, verifiable pass/fail criteria.
11. **Mode of Execution** — how the test is run (e.g. `Manual`,
    `Automated`/bench, as applicable).
12. **Priority** — severity/priority as given or reasonably inferred (see
    `writing-style` skill for the fallback rule).

## Definition of "complete" for QA purposes

A row is structurally valid when: all 12 columns are non-empty, Test Case
ID is unique in the file, Traceability lists only requirement IDs that were
actually extracted as qualifying in this run, and every signal/command
named in Test Input Data / Test Steps / Expected Result was confirmed
during resolution (not invented). A row failing any of these checks should
be flagged by QA, not written to the final output as-is.
