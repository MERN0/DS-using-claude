---
name: resolution-playbook
description: How to resolve a requirement or cluster of requirements against the client's supporting reference documents (signal list, command list, compound command list, application parameters, communication matrix) to find the exact allowed signal/command names and values. Use during the per-cluster resolution phase, before drafting.
---

# Resolution Playbook (default)

The goal of resolution is to turn requirement text (which speaks in
natural language) into the exact, verbatim signal/command/parameter names
and values the client's system actually uses — and nothing else. A client
is only allowed to use the signals/commands defined for them; hallucinated
names make the resulting test case impossible to execute.

## Supporting document types (identify these during discovery, resolve against them here)

- **Signal list** — individual signal names, typically with type/range/unit.
- **Command list** — individual command names, typically with
  parameters/effects.
- **Compound command list** — commands composed of multiple underlying
  commands/signals; check here when a requirement describes a
  multi-step/complex action that doesn't map to a single simple command.
- **Application parameters** — configuration-style values (thresholds,
  timeouts, calibration values) referenced by requirements.
- **Communication matrix** — which signals/commands travel on which
  bus/message, useful for confirming a signal is actually reachable/
  observable in the way the requirement implies.

Not every client provides every type. If a type is entirely absent from
the input directory, proceed without it and note the gap — don't treat it
as a resolution failure for requirements that don't need that type.

## Search procedure per requirement/cluster

1. Pull the key nouns/verbs out of the requirement text (signal-like names,
   command-like phrases, parameter-like values).
2. `search_sheet` the most likely-classified supporting sheet(s) first
   (per discovery.md), trying the term as given.
3. If no match: try variations — partial terms, removing units/qualifiers,
   underscores vs. spaces, common abbreviations. Try a different
   supporting sheet type if the first guess was wrong.
4. Stop after a bounded number of attempts (see `MAX_RESOLUTION_ATTEMPTS`
   in config). If still unresolved, record the item as `unresolved` with
   the search terms you tried — do not substitute a similar-looking name.
5. Record every resolved item with its exact verbatim name, source file,
   sheet, and row, so drafting and QA can both verify it later without
   re-searching.

## Hard constraint

Only signal/command/parameter names that were actually found via this
procedure may appear in a test case's Test Input Data, Test Steps, or
Expected Result. If a requirement can't be fully resolved, still draft the
test case for the parts that *are* resolved, and clearly flag the
unresolved portion rather than silently dropping it or inventing a
plausible name.
