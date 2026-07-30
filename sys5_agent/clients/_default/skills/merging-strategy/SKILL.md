---
name: merging-strategy
description: How to decide which requirement rows should collapse into a single SYS5 test case versus stay separate. Use when clustering extracted requirements before drafting test cases, or when re-evaluating cluster boundaries after signal/command resolution reveals new overlap.
---

# Merging Strategy (default)

Merging is the highest-risk decision in this pipeline: over-merging buries
distinct requirements inside one unreadable test case and under-merging
produces a flood of near-duplicate test cases that re-set up the same
preconditions over and over. Default to caution — when unclear, prefer
fewer, well-justified merges over aggressive ones. This is a quality
judgment, not a quota: never merge (or split) requirements just to hit a
particular test-case count, and never force two requirements into one
cluster because they are topically similar if they don't actually meet one
of the criteria below — a cluster with one requirement in it is a
perfectly fine outcome.

## Merge two or more requirements into one test case when:

1. **Explicit cross-reference** — one requirement's text references
   another requirement's ID, or both explicitly describe the same scenario
   from different angles.
2. **Shared feature/module AND shared precondition** — both requirements
   apply to the same feature/module tag and start from the same system
   state/precondition, so verifying them together avoids redundant setup.
3. **Sequential workflow chain** — adjacent requirements describe a single
   Given/When/Then-style scenario split across rows (e.g. one row sets a
   state, the next row asserts the resulting behavior).
4. **Shared resolved signal/command set** — discovered *after* resolution:
   two requirements manipulate the identical signal(s)/command(s) in the
   same mode/context. If this is discovered after an initial coarse
   cluster was already drafted around different boundaries, revise the
   cluster rather than leaving the overlap unmerged.

## Do NOT merge when:

- Requirements belong to different features/modules with no shared
  precondition or signal.
- Merging would push the cluster past `MAX_REQS_PER_TESTCASE` (check
  config) — split into multiple test cases instead, and make sure the
  split test cases still each carry correct Traceability for their subset.
- The requirements are similar in *topic* but test genuinely different
  behavior (e.g. two requirements both mention the same signal but one is
  about a valid-range check and the other is about an out-of-range fault
  response) — these usually deserve separate test cases even though they
  share a signal.

## Two-pass process

1. **Coarse pass** (before resolution): cluster using requirement text
   alone — cross-references, feature/module tags, sequential chains.
2. **Refinement pass** (after resolution): revisit cluster boundaries now
   that you know the actual signals/commands each requirement resolves to.
   Split a cluster that turns out to mix unrelated signals; merge clusters
   that turn out to share an identical signal/command set. Only do this
   refinement when resolution actually surfaced something the text alone
   didn't show — don't churn clusters without a concrete reason.

Record the requirement IDs in every cluster explicitly; the traceability
coverage check in QA depends on this being complete and accurate.
