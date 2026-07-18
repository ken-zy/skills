# Phase 2: Plan Review

Reviews the implementation plan (`docs/superpowers/plans/*.md`).

## Review Dimensions

Plan review has two halves: alignment with spec (the plan's job is to faithfully
execute the spec) and execution completeness (the plan's job is to be runnable
without surprises).

```
Half A — Alignment with spec (priority)
  A1 — Coverage: Every spec goal mapped to a concrete plan task?
  A2 — Faithfulness: Plan implements spec's direction, or silently substituted?
  A3 — Scope drift: Plan adds work the spec did not ask for?

Half B — Execution completeness
  B1 — Logic gaps: Race conditions, ordering, error handling, sort direction,
       early-stop correctness, helper-method semantics (NOT IN vs IN).
  B2 — Step omissions: Migrations, backfills, doc-sync (grep across tests/ and
       CLAUDE.md for hardcoded constants), rollback path, observability hooks.
  B3 — Code-reference accuracy: For "Modify" files only, line numbers and
       signatures match actual code today. "Create" files don't exist yet —
       do not flag them as missing.
  B4 — Sequencing: Each task's preconditions produced by an earlier task?
```

## Prompt Template

```
You are reviewing an IMPLEMENTATION PLAN. Your job has two halves:
(A) Does the plan stay faithful to the spec's direction?
(B) When executed step by step, will anything be missed or go wrong?

Read these files (in this order):
1. The spec the plan implements: <SPEC_FILE_PATH>
   (If "N/A", skip Half A and note "no spec available" in the output.)
2. The plan: <PLAN_FILE_PATH>
3. <CONVENTION_FILE>
4. Source files referenced in the plan — verify line numbers / signatures for
   files marked "Modify" only. Files marked "Create" do not exist yet;
   do NOT flag them as missing.

=== HALF A: ALIGNMENT WITH SPEC (priority) ===

A1 — Coverage: Does every goal / requirement stated in the spec map to one or
     more concrete tasks in the plan? List anything in the spec that the plan
     does not address.
A2 — Faithfulness: Does the plan implement the spec's chosen direction, or has
     it silently substituted a different approach? (e.g. spec says "event-driven",
     plan introduces polling — that's drift.)
A3 — Scope drift: Does the plan add work the spec did not ask for? Flag every
     extra task / abstraction / configuration knob with no spec basis.

If the plan diverges from the spec, the divergence itself is the issue —
not whether the divergence is "technically better". Spec wins.

=== HALF B: EXECUTION COMPLETENESS ===

B1 — Logic gaps: Race conditions, ordering assumptions, error handling,
     pagination/sort direction, helper-method semantics (NOT IN vs IN),
     early-stop correctness. Verify the algorithm actually works for the
     stated case.
B2 — Step omissions: Migrations, backfills, doc updates, test updates,
     hardcoded-constant grep across tests/ and CLAUDE.md, rollback path,
     observability hooks. What will break in CI or prod that the plan forgot?
B3 — Code-reference accuracy: For "Modify" files only, do referenced line
     numbers, method names, and signatures match the actual code today?
B4 — Sequencing: Are tasks ordered so each task's preconditions are produced
     by an earlier task?

=== WHAT TO IGNORE ===

- Whether the spec's direction itself is correct — that was already reviewed
- Style of the plan document, section ordering, Markdown formatting
- Suggestions to "consider adding X" that the spec did not request — that is
  the same scope creep you are supposed to be CATCHING

=== PRE-MORTEM (mandatory) ===

Assume this plan was executed faithfully and the deliverable failed code review
or shipped a bug. The failure was either (a) a spec goal was silently dropped,
or (b) a step was missing / mis-sequenced. Name the single most likely failure
and cite the spec line it traces back to.

=== OUTPUT ===

For each issue >= 70 confidence: ISSUE format.
Tag each finding with `[ALIGN-A1..A3]` or `[EXEC-B1..B4]` so the author can
tell whether the issue is "you drifted from the spec" or "you'll trip in execution".
Location format: "Task N, Step M" (plan) or "Section: <name>" (spec coverage gap).
If both halves are clean: "LGTM: <one sentence on alignment + one on execution>".
```

`<CONVENTION_FILE>` = "AGENTS.md (project root)" for external backends, "CLAUDE.md (project root)" for subagent.

## ACCEPT Action

Modify the plan file.

## Review Loop Gate — HARD REQUIREMENT

**DO NOT skip Round 2+ after fixing issues.** If ANY issue was ACCEPTED and the plan was modified, you MUST re-dispatch reviewers to verify the fixes and re-evaluate REJECTED issues. Only dimensions that returned LGTM in the previous round can be excluded (early-stop).

```
Round 1: dispatch all dimensions → process ACCEPT/REJECT → modify plan
Round 2: re-dispatch non-LGTM dimensions → verify fixes, re-evaluate REJECTs
...continue until termination condition (see Shared Mechanics)...
```

Termination conditions (from SKILL.md Shared Mechanics — uses issue tracker for "same issue" detection):
- All dimensions LGTM
- All remaining issues REJECTED with no plan modifications
- Same issues persist 2 consecutive rounds → CEO Decision
- Round >= 5 → CEO Decision

**The thought "I fixed the issues, moving to next phase" is a RED FLAG.** Fixes must be verified.

## Next Phase — AUTOMATIC, DO NOT ASK USER

After Plan Review completes (LGTM or CEO Decision) → **immediately** read `execution.md` in this directory and proceed to Execution. No user confirmation. No status summary that waits for input. Just announce "Starting Phase 3: Execution" and continue.
