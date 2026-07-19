# Phase 1: Design Review

Reviews the design spec (`docs/superpowers/specs/*.md`) through the external
reviewer in the explicit tmux pane.

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

Spec review is intentionally narrow: direction only, not implementation detail.

```text
P1 - Problem framing: Right problem? Real need, or solution-in-search-of-problem?
P2 - Directional soundness: Approach fundamentally viable, or structurally flawed?
P3 - Missing alternatives: Obviously better direction not considered?
P4 - Scope sanity (YAGNI): Gold-plating beyond what the stated problem needs?
P5 - Promise audit: casual promise sentences that bind downstream phases to
     machinery the stated problem does not require?
```

Out of scope for this phase: specific signatures, field names, retry counts,
timeouts, minor edge cases, style, wording, section order, and anything that
belongs in plan or code review. Promise sentences are NOT out of scope: a
sentence that reads like a detail but promises semantics is direction (see P5).

## Prompt Template

```text
You are reviewing a DESIGN SPECIFICATION. Your job is to catch DIRECTIONAL errors
before they get baked into a plan and code. You are NOT reviewing implementation.

Read these files:
1. The design spec: <SPEC_FILE_PATH>
2. <CONVENTION_FILE>
3. Existing code the design will touch, only to understand current direction.

Write the complete result to the helper-designated output file. Do not edit any
source/spec/helper/git files.

=== WHAT TO REVIEW (in priority order) ===

P1 - Problem framing: Is the spec solving the RIGHT problem? Is the stated
     user/business need real, or is it a solution looking for a problem?
P2 - Directional soundness: Is the chosen approach fundamentally viable, or does
     it have a structural flaw that no amount of detail-tuning can fix?
P3 - Missing alternatives: Is there an obviously better direction that was not
     considered? State it concretely.
P4 - Scope sanity (YAGNI): Does the spec include features/flexibility that the
     stated problem does NOT require?
P5 - Promise audit: Every promise sentence in this spec becomes a HARD
     requirement downstream -- plan review will force the plan to implement it
     mechanically. Flag any sentence that casually promises scheduling,
     fairness, carry-over, retry, or bookkeeping semantics the stated problem
     does not require. Recommend deleting or narrowing the promise, never
     specifying it further. A promise sentence is direction, not detail, even
     when it is one clause long.

=== WHAT TO IGNORE ===

- Specific API signatures, field names, error codes, retry counts, timeouts
- Edge cases unless they invalidate the entire approach
- "Could be more scalable / observable / testable" suggestions unless the
  current direction makes those properties impossible to add later
- Style, wording, section ordering inside the spec document
- Anything that belongs in plan review or code review

=== PRE-MORTEM (mandatory) ===

Assume this spec was implemented exactly as written and the project failed.
The failure was a directional mistake: wrong problem, wrong approach, or wrong
scope. Name the single most likely directional failure and explain why the spec
invites it.

=== OUTPUT ===

For each directional issue: ISSUE format with confidence scoring.
Tag each finding with [P1], [P2], [P3], [P4], or [P5].
Location format: "Section: <section name>".
If the direction is sound: "LGTM: <one-sentence justification of the direction>".

Calibration: prefer one strong directional finding over five detail nitpicks.
If you find yourself writing "consider adding X for robustness", delete it.
```

`<CONVENTION_FILE>` resolves to `AGENTS.md (project root) -- mandatory; read
before review.` when present. If absent, it resolves to `no convention file
available`, and the active reviewer must state that convention context was
unavailable.

## ACCEPT Action

The primary driver modifies the spec file after VERIFY, EVALUATE, CLASSIFY, and
PREMISE-CHECK.

## Review Loop Gate

Do not skip Round 2+ after fixing issues. If any accepted issue modified the
spec, the primary driver must re-dispatch the external reviewer through the
active tmux helper to verify the fix and re-evaluate rejected issues.

Termination conditions are inherited from `SKILL.md` Shared Review Loop:

- all dimensions LGTM
- all remaining issues rejected with no spec modifications
- same issues persist for two consecutive rounds, then CEO Decision
- Round >= 5, then CEO Decision

## Next Phase

After Design Review completes:

1. If design-only/spec-only mode is ON, go directly to `report.md`. Do not
   create a plan, execute code, create a PR, or run code review.
2. If design-only mode is OFF and no implementation plan exists for the topic,
   the primary driver creates the implementation plan before Plan Review. The
   primary driver skips the plan skill's execution-handoff prompt and internal
   review loop because this skill performs plan review through the external
   reviewer.
3. Announce "Starting Phase 2: Plan Review" and read `plan-review.md`.

No user confirmation. Phase transition is automatic.
