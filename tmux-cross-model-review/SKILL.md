---
name: tmux-cross-model-review
description: Use when coordinating a tmux-based cross-model review lifecycle for a design spec, implementation plan, pull request, or multi-round review. Supports codex-primary mode, where Codex drives and Claude Code reviews through an explicit tmux pane, and claude-primary mode, where Claude Code drives and Codex reviews through an explicit tmux pane.
---

# Tmux Cross-Model Review

Full lifecycle review: **Design Review -> Plan Review -> Execution -> Code Review -> Report**.

Core principle: two models catch more than one, but reviewer output is evidence,
not authority. The primary driver verifies every accepted finding against the
actual repository before changing files.

## Role Modes

```text
codex-primary   # default, current behavior
claude-primary  # Claude Code native session owns the lifecycle
```

If no mode is passed, use codex-primary.

Both modes use the same cross-model interaction shape:

```text
primary session -> prompt file -> explicit tmux reviewer pane -> review result Markdown
```

| Concern | codex-primary | claude-primary |
|---|---|---|
| Primary driver | Codex | Claude Code |
| Artifact owner | Codex | Claude Code |
| External reviewer | Claude Code | Codex |
| Reviewer bridge direction | Codex -> Claude Code over tmux | Claude Code -> Codex over tmux |

In `codex-primary`, Codex writes and executes; Claude Code reviews through
`lib/invoke-claude.sh`.

In `claude-primary`, Claude Code writes and executes; Codex reviews through
`lib/invoke-codex-tmux.sh`.

If Codex receives a request to run `claude-primary`, Codex must not simulate
that mode by driving a Claude pane. Hand off to `claude-primary.md` and tell the
user to run it from a native Claude Code session.

This skill is tmux-only. Use explicit tmux reviewer panes as the backend
primitive. Do not call removed reviewer backends, hidden reviewer processes, or
same-dialog substitutes.

## AUTONOMOUS FLOW -- NON-NEGOTIABLE

Once started, this skill runs through all applicable phases to completion
without user interaction.

Forbidden between start and final report:

- asking whether to continue
- asking whether to start execution
- asking whether to enter the next phase
- any confirmation request between phases

Required user-visible progress before the final report:

- phase announcements, such as "Starting Phase 2: Plan Review"
- round progress, such as "Round 2: 1 issue found, 1 accepted"
- CEO Decisions made inline by Codex
- the two escalation exceptions below (User-Premise Conflict, Boundary
  Conflict)

Phase transitions are automatic:

```text
Full pipeline: design-review.md -> plan-review.md -> execution.md -> code-review.md -> report.md
Design-only:   design-review.md -> report.md
```

## The Two Exceptions -- Escalations That Pause the Flow

Exactly two situations pause the autonomous flow.

### Exception 1 -- User-Premise Conflict Escalation

```text
TRIGGER:
- A Claude Code finding is about to be accepted or applied, and
- applying it would overturn a decision the user made explicitly, or invalidate
  the factual premise behind that decision.

ACTION:
Pause, state the conflicting user decision, state the false premise, cite the
evidence, offer concrete options, and wait for the user.
```

### Exception 2 -- Boundary-Conflict Escalation

```text
TRIGGER:
- A reviewer or primary driver identifies [BOUNDARY-CONFLICT]: an upstream goal
  (spec goal during plan review, plan task during execution or code review)
  cannot be implemented without state or machinery the upstream artifact never
  described.

ACTION:
Pause, cite the upstream sentence that forces the machinery, describe the
machinery it would require, offer the two resolutions -- amend the upstream
artifact to include the machinery, or narrow the upstream promise so the
machinery becomes unnecessary -- and wait for the user.
```

These are escalations, not confirmation prompts. After the user chooses, record
the result as `user-override` in the issue tracker and resume the pipeline from
the paused point.

## Step 1: Select Tmux Reviewer Pane

Before invoking the external reviewer, read `tmux-backend.md`.

For `codex-primary`, the Claude Code target pane must be explicit:

```text
--tmux-pane <target>
CLAUDE_REVIEW_TMUX_PANE=<target>
```

No pane auto-detection is allowed. If no pane is provided, fail with available
pane diagnostics.

The pane must run in `bypassPermissions` or `dontAsk`. `acceptEdits is invalid`
for the full lifecycle because code review requires Bash commands such as
`git diff origin/main --stat`, and the helper cannot answer permission prompts.

For `claude-primary`, the Codex target pane must be explicit:

```text
--codex-tmux-pane <target>
CODEX_REVIEW_TMUX_PANE=<target>
```

The Codex pane must run with effective behavior equivalent to:

```bash
codex --cd /path/to/repo \
  --sandbox workspace-write \
  --ask-for-approval never \
  --no-alt-screen
```

See `claude-primary.md` for the Claude-facing lifecycle entrypoint.

## Step 2: Detect Phase & Load Phase File

Parse explicit phase first:

```text
tmux-cross-model-review design <path>  -> read design-review.md
tmux-cross-model-review plan <path>    -> read plan-review.md
tmux-cross-model-review code           -> read code-review.md
```

If no explicit phase is provided:

1. Extract topic from the current branch name.
2. If on `main` or `master`, stop with a concrete usage message.
3. If an open PR exists on the current branch, read `code-review.md`.
4. If code changes exist versus `origin/main`:
   - changed plan file under `docs/superpowers/plans/` -> read `plan-review.md`
   - otherwise -> read `code-review.md`
5. If a matching plan exists under `docs/superpowers/plans/`, read
   `plan-review.md`.
6. If a matching spec exists under `docs/superpowers/specs/`, read
   `design-review.md`.
7. Otherwise stop with a concrete usage message.

After a phase completes, immediately read the next phase file and continue.

## Termination Mode -- Design-Only / Spec-Only

Design-only mode is ON when either:

- invocation includes `--design-only`, `--spec-only`, `design only`, or
  `spec only`
- the user instruction says review only, do not implement, do not build,
  only review, `只评审`, `不实现`, `不建 repo`, or `不写代码`

When ON, Design Review runs normally and then the pipeline goes straight to
`report.md`. Do not create a plan, execute code, create a PR, or run code
review.

Do not infer design-only from the document contents or filename. Evaluate the
mode once at startup and enforce it at the end of Design Review.

## Prompt Template Variable Injection

Each phase file contains prompt placeholders. Codex resolves them before
dispatching Claude Code:

| Placeholder | Resolved from | Fallback |
|---|---|---|
| `<SPEC_FILE_PATH>` | detected spec path | `N/A` |
| `<PLAN_FILE_PATH>` | detected plan path | `N/A` |
| `<CONVENTION_FILE>` | project root `AGENTS.md` check | `no convention file available` |
| `<PHASE>` | current phase name | hard error |
| `<ROUND>` | current round number | hard error |

Resolve `<CONVENTION_FILE>` before dispatch. If project root AGENTS.md exists, the active reviewer must read it before review. If AGENTS.md is absent, inject and record `no convention file available`.
Missing convention context is allowed, but the round must not be treated as
convention-aware review.

No raw `<...>` placeholder may be sent to Claude Code. If unresolved
placeholders remain in the phase prompt, fail before dispatch.

The review output path is owned by `lib/invoke-claude.sh`. Phase templates refer
only to the helper-designated output file. The helper wrapper injects the
concrete output path and sentinel contract.

## Shared: Review Loop Mechanics

All review phases use these rules.

### Tmux Helper Interface

Create prompt files outside the repository:

```bash
prompt_tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/claude-review-prompt.XXXXXX")"
prompt_file="$prompt_tmp_dir/prompt.md"
```

Do not create temporary prompt files under the repository or under docs/reviews.
The prompt file may be Markdown, but it is transient input for the helper, not a
review artifact.

Review results are Markdown files under `docs/reviews/claude-code/YYYYMMDD/*.md`.
Those result files are the only repo-local Markdown artifacts the reviewer is
allowed to create by default.

Round 1:

```bash
/Users/jdy/Documents/skills/tmux-cross-model-review/lib/invoke-claude.sh \
  --phase <PHASE> \
  --round 1 \
  --cwd /path/to/repo \
  --prompt-file "$prompt_file" \
  --tmux-pane <target> \
  --timeout-seconds 900 \
  --poll-seconds 5
```

Round N:

```bash
/Users/jdy/Documents/skills/tmux-cross-model-review/lib/invoke-claude.sh \
  --phase <PHASE> \
  --round <ROUND> \
  --cwd /path/to/repo \
  --prompt-file "$prompt_file" \
  --tmux-pane <target> \
  --timeout-seconds 900 \
  --poll-seconds 5
```

The result file is the source of truth. Pane scrollback is diagnostics only.

For `claude-primary`, Claude Code uses the Codex reviewer helper:

```bash
/Users/jdy/Documents/skills/tmux-cross-model-review/lib/invoke-codex-tmux.sh \
  --preflight \
  --cwd /path/to/repo \
  --codex-tmux-pane <target> \
  --timeout-seconds 900 \
  --poll-seconds 5
```

Then each Codex review round uses:

```bash
/Users/jdy/Documents/skills/tmux-cross-model-review/lib/invoke-codex-tmux.sh \
  --phase <PHASE> \
  --round <ROUND> \
  --cwd /path/to/repo \
  --prompt-file "$prompt_file" \
  --codex-tmux-pane <target> \
  --timeout-seconds 900 \
  --poll-seconds 5
```

Codex reviewer results are Markdown files under `docs/reviews/codex/YYYYMMDD/*.md`.
Those files must contain:

```text
CODEX_REVIEW_RESULT_V1
CODEX_REVIEW_DONE
```

### Convention File Rule

If project root AGENTS.md exists, the active reviewer must read it before review. If AGENTS.md is absent, inject and record `no convention file available`.
The review may proceed without a convention file, but the final report must
preserve that fact instead of presenting the round as convention-aware.

### Confidence Filtering

Use this scale:

```text
0=false positive  25=might be real  50=real but minor
70=verified real  85=double-checked important  100=certain failure
```

Only issues with confidence `>= 70` enter ACCEPT/REJECT processing.

### Context Budget

If one reviewer output exceeds 16000 characters, summarize it before
continuing. Preserve phase, location, issue, confidence, and evidence.

If accumulated review context exceeds 48000 characters, compress older rounds
into a ledger:

```text
phase, dimension, location, status, confidence, one-line summary
```

### Issue Tracker

Maintain a lightweight issue tracker across rounds within each phase:

```text
[phase, dimension, location, one-line summary, status, confidence]
```

Status values:

```text
open
accepted
rejected
ceo-accepted
ceo-rejected
ceo-compromised
user-override
```

The tracker is included in Round N prompts and in the final report.

### Response Protocol

For each Claude Code issue at confidence `>= 70`:

1. VERIFY against the actual current artifact.
2. BOUNDARY-CHECK: if verification shows the issue is a [BOUNDARY-CONFLICT] --
   whether tagged by the reviewer or identified by the primary driver -- UPDATE
   the issue tracker, escalate via Exception 2, and stop processing this issue.
   Never ACCEPT or REJECT a confirmed [BOUNDARY-CONFLICT]. If the boundary claim
   is not confirmed, continue with the normal protocol below.
3. EVALUATE whether the issue is technically correct for this project.
4. CLASSIFY as bug, missing requirement, intentional tradeoff, false positive,
   or user-premise conflict.
5. PREMISE-CHECK: would accepting it overturn an explicit user decision or the
   factual premise behind that decision?
   - yes -> escalate via Exception 1 before applying any fix
   - no -> continue
6. UPDATE the issue tracker.
7. ACCEPT or REJECT.

Never blindly accept reviewer feedback. The external reviewer cannot be the
final authority over primary-owned changes.

### Round N > 1 Prompt

Round N prompts are incremental:

```text
Before responding, re-read these modified files:
<files changed since last round>

The author reviewed your previous issues and responded:

ACCEPTED:
- <issue> -- Modified as: <specific change>

REJECTED:
- <issue> -- Reasoning: <evidence>

Re-evaluate rejected issues. Withdraw if the pushback is sound.
If you still disagree, provide new concrete evidence.
Also check whether accepted modifications introduced new problems.
Only report issues with confidence >= 70.
```

Do not resend the full artifact unless the pane context was lost or the phase
file requires it.

Fast-REJECT rule: if Claude Code re-raises an already rejected issue without new
concrete evidence, Codex rejects it immediately. A stale re-raise alone does not
force a CEO Decision. CEO fires only when all remaining open issues in the round
are such stale re-raises, which satisfies the "same issues repeated for two
consecutive rounds" termination condition.

### Termination

| Condition | Action |
|---|---|
| LGTM | next phase |
| all remaining issues rejected and no modifications | next phase |
| same issues repeated for two consecutive rounds | CEO Decision, then next phase |
| Round >= 4 and all open issues are verification requests below threshold | LGTM early exit, then next phase |
| Round >= 5 | CEO Decision, then next phase |

### CEO Decision

For each disagreement:

1. PRE-CHECK: if resolving it would overturn the user's explicit decision or the
   factual premise behind it, escalate via Exception 1.
2. Summarize Codex's argument and evidence.
3. Summarize Claude Code's argument and evidence.
4. Decide which outcome serves the project long term.
5. Verdict: ACCEPT, REJECT, or COMPROMISE.
6. Write the rationale in one or two sentences.

Codex does not default to either side.

post-CEO verification: if a CEO ACCEPT or COMPROMISE modifies an artifact, Codex
performs a lightweight single-pass self-check of the resulting diff. Any
regression fix still goes through PREMISE-CHECK. Unverified CEO changes are
flagged as `unreviewed` in the report.

### Phase Transition Checks

```text
Phase 1 -> 2: if the spec changed, check whether an existing plan is stale.
Phase 2 -> 3: re-read the updated plan before executing.
Phase 3 -> 4: verify all plan tasks are complete before PR/code review.
```

Transition is automatic. Do not output anything that waits for user input.

### Fix Discipline: Root Cause First

When accepting a reviewer issue, fix the root cause in one pass. Do not make
incremental approximations that let Claude Code chase the same issue across
rounds.

Before modifying an artifact for an accepted issue, ask:

1. Can this issue be dissolved by narrowing the requirement or shrinking the
   input set, instead of adding mechanism? If the narrowing changes an
   upstream artifact (spec or plan), that is Exception 2 -- escalate. Prefer
   narrowing over mechanism whenever both resolve the issue.
2. What is the fundamental requirement this issue points to?
3. Does the fix address that requirement directly?
4. Would Claude Code likely find a flaw in the approximation next round?

If the answer to the fourth question is "maybe", go deeper before re-dispatch
-- but only within the upstream artifact's boundary. If going deeper would
introduce state or machinery the upstream artifact never described, stop and
escalate via Exception 2 instead.

### Tmux Helper Failure Handling

If `lib/invoke-claude.sh` exits non-zero, exits `124`, reports a permission
prompt, or returns an output file without required sentinels:

1. Retry once with the same pane and a new output file.
2. If Round 1 fails twice, stop the Claude-backed phase and report the failure.
3. If Round N fails twice, keep the issue tracker and run a local Codex review
   of the changed files before deciding whether to proceed.

Review failure is not LGTM.

## Red Flags

| Thought | Reality |
|---|---|
| "Maybe the helper can choose a pane" | No. Provide an explicit tmux pane. |
| "acceptEdits should be enough" | No. `acceptEdits is invalid` for code review because Bash may prompt. |
| "Reviewer found it, so fix it" | VERIFY, EVALUATE, CLASSIFY, PREMISE-CHECK first. |
| "I fixed it, move on" | No. Accepted modifications require Round 2+. |
| "Should I ask whether to continue?" | No. Phase transitions are automatic except the two escalation exceptions. |
| "Review failed, but probably fine" | No. Review failure is not LGTM. |
| "Pane scrollback has the answer" | No. Read the helper-designated result file. |
