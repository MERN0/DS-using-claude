---
name: writing-style
description: Default phrasing, tense, terminology, and formatting conventions for writing SYS5 test case fields (objective, description, precondition, steps, expected result) -- including the fixed numbering scheme and the check-type-driven wording for boundary/invalid-values/functionality/stress/load test cases. Use during test-case drafting. Client directories may override this skill with their own house style.
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

## Fixed numbering scheme (applies to Test Precondition, Test Steps, Expected Result)

All three of these fields are a **numbered list, one item per line**,
written as plain `1.`, `2.`, `3.`, ... — never `Step 1`, `Step 2`, `i.`,
`a)`, bullets (`-`/`•`), or any other style. Use the exact same numbering
style in every test case in the run; do not vary it row to row. Each
numbered item is exactly **one sentence** (or, in Test Steps/Expected
Result, one atomic command — see below), and items are separated by a
literal newline (`\n`), not semicolons or commas run together on one line.
A single-item field is still written as `1. <the one item>`, not left
unnumbered.

## Test Steps: SET / WAIT / VERIFY command syntax (mandatory)

Test Steps must be written as a numbered sequence of atomic commands using
**only these three verbs**. Never write a step as a free-text sentence or
narrative instruction; if an action doesn't reduce to one of these three,
split it into more steps until it does.

- `SET <alias>, <parameter(s)>` — apply a value to a signal/command.
  e.g. `1. SET DoorLockCmd, LOCK`
- `WAIT <duration>` — pause a fixed time before the next command.
  e.g. `2. WAIT 500ms`
- `VERIFY <alias>, <expected parameter(s)>` — read back and check a
  signal/response.
  e.g. `3. VERIFY DoorLockStatus, LOCKED`

Rules:

- One command per step, numbered (`1.`, `2.`, `3.`, ...), no bundling. See
  the fixed numbering scheme above.
- `<alias>` is the short alias/name the signal or command is resolved to
  (see resolution-playbook) — **never** the full technical ID, message ID,
  address, or raw signal definition. If a supporting document only exposes
  an ID and no separate alias/name, use the resolution-playbook's fallback,
  not the ID.
- No prose, no conjunctions ("and then"), no adjectives — parameters are
  exact resolved values/units, not descriptions ("a high value" is
  forbidden; the resolved value is not).

## Expected Result: every Test Step gets a matching line (mandatory)

**Every** Test Steps line — `SET`, `WAIT`, and `VERIFY` alike — must have a
corresponding Expected Result line using the identical step number. Test
Steps and Expected Result always have the same line count, numbered `1.`
through `N.` in lockstep; a step with no expected-result line (or an
expected-result line with no matching step) is incomplete. Each line is
one sentence and uses only the resolved alias/parameters — no vague
language like "works correctly".

- After a `SET` step: state the resulting state as confirmed by that same
  alias (or its paired status alias if resolution recorded one) —
  e.g. step `1. SET DoorLockCmd, LOCK` → `1. DoorLockCmd is set to LOCK.`
  Never invent a status alias resolution didn't actually confirm; if none
  exists, restate the applied value itself as the expected outcome.
- After a `WAIT` step: state that the duration elapses before the next
  command — e.g. step `2. WAIT 500ms` → `2. 500ms elapses.`
- After a `VERIFY` step: restate the identical
  `VERIFY <alias>, <expected parameter(s)>` form —
  e.g. step `3. VERIFY DoorLockStatus, LOCKED` →
  `3. VERIFY DoorLockStatus, LOCKED.`

## Check-type-driven wording

Every test case is drafted for one or more of the fixed check types (see
`CHECK_TYPES` in config; a cluster's applicable type(s) come from
requirement extraction / merge planning, never invented at drafting time).
The check type shapes the values used in Test Input Data/Test
Steps/Expected Result and the Test Case Objective — but every value used
must still be resolution-confirmed; a check type never justifies
inventing a value, fault signal, or error response that wasn't actually
found in a supporting document. If the needed extreme/invalid/error-path
value isn't resolvable, draft what is resolvable and flag the gap per the
resolution-playbook rather than fabricating it.

- **Boundary Value Check**: exercises the min/max/just-inside/
  just-outside values of the resolved allowed range for the signal(s)
  involved. Objective states which boundary is being verified.
- **Invalid Values Check**: applies a value outside the resolved allowed
  range or an otherwise malformed input, and verifies the system's
  documented rejection/fault/error response — only if resolution actually
  found that response signal; otherwise flag as unresolved rather than
  assuming a generic error behavior.
- **Functionality Check**: exercises nominal, in-range values to verify
  the requirement's normal documented behavior. This is the default check
  type when a requirement doesn't call for boundary/invalid/stress/load
  treatment.
- **Stress Test**: repeats an action or sustains a state over an extended
  duration/cycle count (expressed via repeated `SET`/`WAIT`/`VERIFY`
  steps, still following the fixed numbering scheme), verifying the
  behavior holds under sustained/repeated operation.
- **Load Test**: exercises the signal(s)/command(s) under concurrent or
  rapid successive operation, to the extent expressible via
  `SET`/`WAIT`/`VERIFY` steps, verifying the system still behaves
  correctly under that load.

## Field-by-field guidance

- **Test Case Objective**: one sentence, states *why* this test exists
  (which requirement behavior it verifies) and, briefly, which check
  type it targets.
- **Test Case Description**: 1-3 sentences, broader context — what
  scenario/feature this test exercises, referencing the merged
  requirements if applicable.
- **Test Precondition**: numbered list (see the fixed numbering scheme
  above) of system state that must hold before Test Steps begin (mode,
  prior signal states, ignition/power state, etc. as found in the
  requirements/resolution) — one clause per line, each a single sentence.
- **Test Input Data**: the resolved alias(es) and the exact values/ranges to
  be applied — alias + parameters only, never a raw ID or full definition,
  and never a description.
- **Test Steps**: numbered `SET`/`WAIT`/`VERIFY` commands only — see the
  mandatory syntax above. No sentences.
- **Expected Result**: one line per Test Steps line, same numbering — see
  "Expected Result: every Test Step gets a matching line" above. No vague
  language like "works correctly"; the expected value itself is the
  result.
- **Priority**: only use values actually implied or stated by the source
  requirement (e.g. severity/ASIL/priority tags found in the sheet); if
  none is given, use `Medium` and note the assumption in the QA report
  rather than inventing a rationale. A test case marked `Critical` gets the
  extra QA retry budget described in the orchestrator's rules — an
  unresolvable critical item is marked incomplete in-place (see
  `output-format`), never silently dropped.
- **Mode of Execution**: `Manual` unless the source documents indicate the
  requirement is intended for automated/bench execution.
