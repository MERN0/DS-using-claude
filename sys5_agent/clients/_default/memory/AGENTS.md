# SYS5 Test Case Generation — Baseline Rules (all clients)

You are generating System Qualification Test Cases (SYS5) from a System
Requirements Document (SYS2) plus whatever supporting reference files exist
in the client's data directory. These rules apply to every client and are
always loaded — keep them in mind on every turn.

## Non-negotiable rules

1. **Never invent a signal, command, parameter, or value.** Every signal,
   command, compound command, application parameter, or communication
   matrix entry you reference in a test case must have been found verbatim
   in one of the supporting documents during resolution. If you cannot find
   it after a reasonable search, mark the item `unresolved` and say so in
   the QA report — never guess a plausible-looking name.
2. **No test case may be produced from a requirement row that was never
   actually flagged as needing one.** Only rows carrying a SYS5/system
   qualification marker (see below) qualify. Headings, notes, and
   informational rows are not requirements.
3. **Every qualifying requirement must end up traceable to at least one
   test case.** If you merge several requirements into one test case, all
   of their IDs must appear in that test case's Traceability field.
4. **The output has exactly 12 fixed columns, in a fixed order** (see the
   `output-format` skill for the full field-by-field contract). Do not add,
   remove, or rename columns.
5. Sheet names, file names, and column layouts are **not standardized**
   across clients or even within one client's workbook. Confirm what a
   sheet actually contains (via preview) before trusting a guess based on
   its name.

## Recommended phase order (adapt as needed)

Discovery → chunked requirement extraction → merge planning (coarse) →
per-cluster resolution against supporting docs → merge refinement (if
resolution reveals signal/precondition overlap not obvious from text) →
drafting → QA validation → (bounded retry of flagged clusters) → write
output workbook → write run summary.

This is a starting checklist, not a rigid pipeline — skip, reorder, or
repeat phases when the actual data calls for it (e.g. a client with no
compound-command sheet at all, or a requirements file that's already
pre-filtered to only qualifying rows).

## Load skills for detail

Do not try to hold every rule in your head at once — the `merging-strategy`,
`writing-style`, `resolution-playbook`, and `output-format` skills carry the
detailed procedures for each phase. Read the relevant skill before starting
that phase of work.
