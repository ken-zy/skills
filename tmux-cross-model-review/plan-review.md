# Phase 2: Plan Review

Reviews the implementation plan (`docs/superpowers/plans/*.md`) through the
external reviewer in the explicit tmux pane.

## Role Mode Banner

Each resolved prompt starts with one of these banners:

```text
ROLE MODE: codex-primary
Codex is the primary driver and artifact owner. Claude Code is reviewer only.
Codex owns the lifecycle loop.
```

```text
ROLE MODE: claude-primary
Claude Code is the primary driver and artifact owner. Codex is reviewer only.
Claude Code owns the lifecycle loop.
```

## Review Dimensions

Plan review has two halves: alignment with the spec and execution completeness.

```text
Half A - Alignment with spec
  A1 - Coverage: every spec goal mapped to a concrete plan task?
  A2 - Faithfulness: plan implements the spec's direction?
  A3 - Scope drift: plan adds work the spec did not ask for?

Half B - Execution completeness
  B1 - Logic gaps: ordering, error handling, helper semantics, early stops
  B2 - Step omissions: tests, docs, rollback, observability, hardcoded values
  B3 - Code-reference accuracy for files marked Modify
  B4 - Sequencing: each task's preconditions produced earlier?
```

## Prompt Template

```text
You are reviewing an IMPLEMENTATION PLAN. Your job has two halves:
(A) Does the plan stay faithful to the spec's direction?
(B) When executed step by step, will anything be missed or go wrong?

Read these files in order:
1. The spec the plan implements: <SPEC_FILE_PATH>
   If "N/A", skip Half A and note "no spec available" in the output.
2. The plan: <PLAN_FILE_PATH>
3. <CONVENTION_FILE>
4. Source files referenced in the plan. For files marked Modify, verify line
   numbers and signatures. Files marked Create do not exist yet; do not flag
   them as missing.

Write the complete result to the helper-designated output file. Do not edit any
source/spec/helper/git files.

=== HALF A: ALIGNMENT WITH SPEC (priority) ===

A1 - Coverage: Does every spec goal map to one or more concrete tasks?
A2 - Faithfulness: Does the plan implement the spec's chosen direction, or has
     it silently substituted a different approach?
A3 - Scope drift: Does the plan add work the spec did not ask for?

If the plan diverges from the spec, the divergence itself is the issue. Spec wins.

=== HALF B: EXECUTION COMPLETENESS ===

B1 - Logic gaps: ordering assumptions, error handling, pagination/sort
     direction, helper-method semantics, early-stop correctness.
B2 - Step omissions: migrations, backfills, doc updates, test updates,
     hardcoded-constant grep, rollback path, observability hooks.
B3 - Code-reference accuracy: for Modify files only, do referenced line
     numbers, method names, and signatures match the actual code today?
B4 - Sequencing: Are tasks ordered so each task's preconditions are produced by
     an earlier task?

=== WHAT TO IGNORE ===

- Whether the spec's direction itself is correct
- Style of the plan document, section ordering, Markdown formatting
- Suggestions to add work that the spec did not request

=== PRE-MORTEM (mandatory) ===

Assume this plan was executed faithfully and the deliverable failed code review
or shipped a bug. The failure was either a spec goal was dropped or a step was
missing/mis-sequenced. Name the single most likely failure and cite the spec
section it traces back to.

=== OUTPUT ===

For each issue >= 70 confidence: ISSUE format.
Tag each finding with [ALIGN-A1..A3] or [EXEC-B1..B4].
Location format: "Task N, Step M" or "Section: <name>".
If both halves are clean: "LGTM: <one sentence on alignment + one on execution>".
```

`<CONVENTION_FILE>` resolves to `AGENTS.md (project root) -- mandatory; read
before review.` when present. If absent, it resolves to `no convention file
available`, and the active reviewer must state that convention context was
unavailable.

## ACCEPT Action

The primary driver modifies the plan file after VERIFY, EVALUATE, CLASSIFY, and
PREMISE-CHECK.

## Review Loop Gate

Do not skip Round 2+ after fixing issues. If any accepted issue modified the
plan, the primary driver must re-dispatch the external reviewer through the
active tmux helper to verify the fix and re-evaluate rejected issues.

Termination conditions are inherited from `SKILL.md` Shared Review Loop.

## Next Phase

After Plan Review completes, announce "Starting Phase 3: Execution", read
`execution.md`, and proceed automatically. No user confirmation.
