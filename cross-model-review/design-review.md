# Phase 1: Design Review

Reviews the design spec (`docs/superpowers/specs/*.md`).

## Review Dimensions

Spec review is intentionally narrow — direction only, not detail.

```
P1 — Problem framing: Right problem? Real need, or solution-in-search-of-problem?
P2 — Directional soundness: Approach fundamentally viable, or structurally flawed?
P3 — Missing alternatives: Obviously better direction not considered?
P4 — Scope sanity (YAGNI): Gold-plating beyond what the stated problem needs?
P5 — Promise audit: Casual promise sentences that bind downstream phases to
     machinery the stated problem does not require?
```

**Out of scope for this phase:** specific signatures, edge cases, performance
numbers, observability — those belong in plan / code review. Promise sentences
are NOT out of scope: a sentence that reads like a detail but promises
semantics is direction (see P5).

## Prompt Template

```
You are reviewing a DESIGN SPECIFICATION. Your job is to catch DIRECTIONAL errors
before they get baked into a plan and code. You are NOT reviewing implementation.

Read these files:
1. The design spec: <SPEC_FILE_PATH>
2. <CONVENTION_FILE>
3. Existing code the design will touch — ONLY to understand current direction,
   NOT to nitpick how the new design should integrate at line level.

=== WHAT TO REVIEW (in priority order) ===

P1 — Problem framing: Is the spec solving the RIGHT problem? Is the stated
     user/business need real, or is it a solution looking for a problem?
P2 — Directional soundness: Is the chosen approach fundamentally viable, or does
     it have a structural flaw that no amount of detail-tuning can fix?
     (e.g. wrong abstraction layer, wrong data ownership, wrong sync/async choice)
P3 — Missing alternatives: Is there an obviously better direction that wasn't
     considered? State it concretely — "X would be simpler/safer because Y".
P4 — Scope sanity (YAGNI): Does the spec include features/flexibility that the
     stated problem does NOT require? Flag every piece of gold-plating.
P5 — Promise audit: Every promise sentence in this spec becomes a HARD
     requirement downstream — plan review will force the plan to implement it
     mechanically. Flag any sentence that casually promises scheduling,
     fairness, carry-over, retry, or bookkeeping semantics the stated problem
     does not require. Recommend deleting or narrowing the promise, never
     specifying it further. A promise sentence is direction, not detail, even
     when it is one clause long.

=== WHAT TO IGNORE ===

- Specific API signatures, field names, error codes, retry counts, timeouts
- Edge cases unless they invalidate the entire approach
- "Could be more scalable / more observable / more testable" suggestions —
  unless the current direction makes those properties IMPOSSIBLE to add later
- Style, wording, section ordering inside the spec document
- Anything that belongs in plan review or code review

=== PRE-MORTEM (mandatory) ===

Assume this spec was implemented exactly as written and the project failed.
The failure was NOT "we forgot an edge case" — it was a directional mistake:
wrong problem, wrong approach, wrong scope. Name the single most likely
directional failure and explain why the spec invites it.

=== OUTPUT ===

For each directional issue: ISSUE format with confidence scoring.
Tag each finding with `[P1]`, `[P2]`, `[P3]`, `[P4]`, or `[P5]`.
Location format: "Section: <section name>"
If the direction is sound: "LGTM: <one-sentence justification of the direction>"

Calibration: prefer ONE strong directional finding over five detail nitpicks.
If you find yourself writing "consider adding X for robustness", DELETE it —
that is not directional, that is over-design.
```

`<CONVENTION_FILE>` = "AGENTS.md (project root)" for external backends, "CLAUDE.md (project root)" for subagent.

## ACCEPT Action

Modify the spec file.

## Review Loop Gate — HARD REQUIREMENT

**DO NOT skip Round 2+ after fixing issues.** If ANY issue was ACCEPTED and the spec was modified, you MUST re-dispatch reviewers to verify the fixes and re-evaluate REJECTED issues. Only dimensions that returned LGTM in the previous round can be excluded (early-stop).

```
Round 1: dispatch all dimensions → process ACCEPT/REJECT → modify spec
Round 2: re-dispatch non-LGTM dimensions → verify fixes, re-evaluate REJECTs
...continue until termination condition (see Shared Mechanics)...
```

Termination conditions (from SKILL.md Shared Mechanics — uses issue tracker for "same issue" detection):
- All dimensions LGTM
- All remaining issues REJECTED with no spec modifications
- Same issues persist 2 consecutive rounds → CEO Decision
- Round >= 5 → CEO Decision

**The thought "I fixed the issues, moving to next phase" is a RED FLAG.** Fixes must be verified.

## Next Phase — AUTOMATIC, DO NOT ASK USER

After Design Review completes (LGTM or CEO Decision):

**FIRST — Design-only check (see SKILL.md "Termination Mode"):** If design-only /
spec-only mode is ON (explicit flag, or the user said "review only / don't implement
/ 不实现 / 不建 repo"), STOP here: skip all steps below, go straight to `report.md`.
Do NOT create a plan and do NOT write code. Announce: "Design-only mode → terminating
after Design Review, generating report." Everything below applies ONLY to the full pipeline.

1. **Check if an implementation plan already exists** for the reviewed spec:
   ```
   ls docs/superpowers/plans/*<topic>*.md
   ```
2. **If spec was modified during review** and a plan exists, verify the plan doesn't reference stale spec content. Flag any stale references for Phase 2 to address.
3. **If no plan exists → create one first:**
   - **REQUIRED SUB-SKILL:** Use `superpowers:writing-plans` to create the implementation plan
   - **CRITICAL OVERRIDE:** When invoking writing-plans from within cross-model-review, **SKIP the "Execution Handoff" section entirely** — do NOT ask the user to choose between subagent-driven or inline execution. Also skip the plan's own internal review loop (plan-document-reviewer) since cross-model-review will handle review via Codex.
   - Just write the plan, save it, and proceed directly to Plan Review.
4. **Announce:** "Starting Phase 2: Plan Review" and read `plan-review.md` in this directory.

No user confirmation. No status summary that waits for input. No execution choice questions.
