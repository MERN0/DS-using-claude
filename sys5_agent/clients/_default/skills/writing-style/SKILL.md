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

- **Tense**: imperative for steps ("Set signal X to 5"), present tense for
  objective/description/expected result ("Verifies that...", "The system
  shall...").
- **Numbering**: Test Steps is a numbered list, one discrete action per
  step (`1. ...`, `2. ...`). Do not bundle multiple actions into one step.
- **No pronouns for the system under test** — name it explicitly or call it
  "the system"/"the ECU"/the applicable unit name found in the source
  documents, consistently within a test case.
- **Units and exact values always included** — never "set the signal to a
  high value", always "set signal `<Signal Name>` to `<exact value/unit>`"
  using the name/value found during resolution.
- **No invented terminology** — use the exact signal/command/parameter
  names as they appear in the supporting documents, not paraphrased or
  abbreviated versions.

## Field-by-field guidance

- **Test Case Objective**: one sentence, states *why* this test exists
  (which requirement behavior it verifies).
- **Test Case Description**: 1-3 sentences, broader context — what
  scenario/feature this test exercises, referencing the merged
  requirements if applicable.
- **Test Precondition**: bulleted list of system state that must hold
  before Test Steps begin (mode, prior signal states, ignition/power state,
  etc. as found in the requirements/resolution).
- **Test Input Data**: concrete signal/command names and the exact
  values/ranges to be applied, as resolved — not descriptions.
- **Test Steps**: numbered, imperative, one action per step, ending in a
  clear observation point.
- **Expected Result**: precise, verifiable outcome per step or overall —
  avoid vague language like "works correctly"; state the exact expected
  signal/response value.
- **Priority**: only use values actually implied or stated by the source
  requirement (e.g. severity/ASIL/priority tags found in the sheet); if
  none is given, use `Medium` and note the assumption in the QA report
  rather than inventing a rationale.
- **Mode of Execution**: `Manual` unless the source documents indicate the
  requirement is intended for automated/bench execution.
