---
name: writing-style
description: Default phrasing, tense, terminology, and formatting conventions for writing SYS5 test case fields (objective, description, precondition, steps, expected result). Use during test-case drafting. Client directories may override this skill with their own house style.
---

# Writing Style (default / industry-standard baseline)

Used whenever a client hasn't provided its own `writing-style` override.
Keep language precise, testable, and free of ambiguity — a qualification
engineer executing this test case at the client's site should never have to
guess what to do or what counts as pass/fail.

## General conventions

- **Tense**: present tense for objective/description ("Verifies that...",
  "The system shall...").
- **No pronouns for the system under test** — name it explicitly or call it
  "the system"/"the ECU"/the applicable unit name found in the source
  documents, consistently within a test case.
- **Units and exact values always included** — never "set the signal to a
  high value", always the exact alias and value/unit found during
  resolution.
- **No invented terminology** — use only the exact signal/command alias and
  parameters as resolved, not paraphrased or abbreviated versions.

## Test Steps: SET / WAIT / VERIFY command syntax (mandatory)

Test Steps — and the VERIFY lines restated in Expected Result — must be
written as a numbered sequence of atomic commands using **only these three
verbs**. Never write a step as a free-text sentence or narrative
instruction; if an action doesn't reduce to one of these three, split it
into more steps until it does.

- `SET <alias>, <parameter(s)>` — apply a value to a signal/command.
  e.g. `1. SET DoorLockCmd, LOCK`
- `WAIT <duration>` — pause a fixed time before the next command.
  e.g. `2. WAIT 500ms`
- `VERIFY <alias>, <expected parameter(s)>` — read back and check a
  signal/response.
  e.g. `3. VERIFY DoorLockStatus, LOCKED`

Rules:

- One command per step, numbered (`1.`, `2.`, `3.`, ...), no bundling.
- `<alias>` is the short alias/name the signal or command is resolved to
  (see resolution-playbook) — **never** the full technical ID, message ID,
  address, or raw signal definition. If a supporting document only exposes
  an ID and no separate alias/name, use the resolution-playbook's fallback,
  not the ID.
- No prose, no conjunctions ("and then"), no adjectives — parameters are
  exact resolved values/units, not descriptions ("a high value" is
  forbidden; the resolved value is not).
- **Expected Result** restates each terminal `VERIFY` step's outcome using
  the identical `<step-number>. VERIFY <alias>, <expected parameter(s)>`
  form — one line per check if a test case has more than one. It must not
  contain narrative text either.

## Field-by-field guidance

- **Test Case Objective**: one sentence, states *why* this test exists
  (which requirement behavior it verifies).
- **Test Case Description**: 1-3 sentences, broader context — what
  scenario/feature this test exercises, referencing the merged
  requirements if applicable.
- **Test Precondition**: bulleted list of system state that must hold
  before Test Steps begin (mode, prior signal states, ignition/power state,
  etc. as found in the requirements/resolution).
- **Test Input Data**: the resolved alias(es) and the exact values/ranges to
  be applied — alias + parameters only, never a raw ID or full definition,
  and never a description.
- **Test Steps**: numbered `SET`/`WAIT`/`VERIFY` commands only — see the
  mandatory syntax above. No sentences.
- **Expected Result**: the `VERIFY` line(s) restated with expected
  parameters — see the mandatory syntax above. No vague language like
  "works correctly"; the expected value itself is the result.
- **Priority**: only use values actually implied or stated by the source
  requirement (e.g. severity/ASIL/priority tags found in the sheet); if
  none is given, use `Medium` and note the assumption in the QA report
  rather than inventing a rationale. A test case marked `Critical` gets the
  extra QA retry budget described in the orchestrator's rules — an
  unresolvable critical item is marked incomplete in-place (see
  `output-format`), never silently dropped.
- **Mode of Execution**: `Manual` unless the source documents indicate the
  requirement is intended for automated/bench execution.
