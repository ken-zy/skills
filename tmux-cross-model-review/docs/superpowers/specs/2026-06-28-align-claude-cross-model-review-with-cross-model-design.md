# Design: Align claude-cross-model-review With cross-model-review

Date: 2026-06-28

## Problem

`claude-cross-model-review` is currently a tmux-only Claude Code reviewer helper.
It can dispatch review prompts, collect a sentinel-delimited result file, and
guard against unintended file changes. That is useful, but it is not equivalent
to `/Users/jdy/Documents/skills/cross-model-review`.

The target is architectural parity with `cross-model-review`: a full autonomous
review lifecycle with phase detection, multi-round review loops, issue tracking,
phase transitions, execution, code review, and final reporting.

The user requirement is:

- Use `/Users/jdy/Documents/skills/cross-model-review` as the source architecture.
- Preserve all workflow behavior unless it is directly tied to the reviewer
  backend or the model roles.
- The only intentional differences are:
  - Backend: use an existing Claude Code tmux pane instead of Codex companion or
    Claude subagents.
  - Roles: Codex is the orchestrator / implementer, Claude Code is the external
    reviewer.

## Current Gap

The current `claude-cross-model-review` skill has these useful pieces:

- `SKILL.md` with tmux invocation instructions and embedded phase prompt
  templates.
- `tmux-backend.md` with pane requirements, output contract, and side-effect
  guard rules.
- `lib/invoke-claude.sh` as the tmux dispatch helper.
- `tests/test-invoke-claude-tmux.sh` covering helper behavior.

It is missing the `cross-model-review` lifecycle shape:

- autonomous flow and the "ONE Exception" escalation rule
- backend detection / phase detection / design-only mode
- prompt placeholder injection
- per-phase files for design, plan, execution, code, and report
- shared issue tracker across rounds
- full response protocol: VERIFY, EVALUATE, CLASSIFY, PREMISE-CHECK, UPDATE
- fast-reject rule, CEO decisions, and post-CEO verification
- phase transition checks
- execution phase
- PR/code-review phase automation and safety net
- final structured report

## Design Goal

Convert `claude-cross-model-review` from a reviewer helper into a
role-inverted clone of `cross-model-review`.

The new skill must feel familiar to someone who knows `cross-model-review`.
When a behavior exists in `cross-model-review`, the default answer is "copy the
behavior and substitute backend / role nouns." Any deviation must be explicitly
documented as a tmux or model-role difference.

## Non-Goals

- Do not keep the current simplified helper-only design as the main workflow.
- Do not support the removed Claude CLI backend.
- Do not add hidden pane auto-detection. The target pane remains explicit.
- Do not introduce a new review framework unrelated to `cross-model-review`.
- Do not implement this spec in the design step. Implementation will be planned
  separately after review.

## Source Architecture To Mirror

Mirror these files from `/Users/jdy/Documents/skills/cross-model-review`:

```text
SKILL.md
design-review.md
plan-review.md
execution.md
code-review.md
report.md
```

Backend-specific docs differ:

```text
cross-model-review/subagent-backend.md
claude-cross-model-review/tmux-backend.md
```

`subagent-backend.md` is not copied as a runtime backend because this skill is
tmux-only. Its relevant orchestration ideas can be referenced only where they
map to tmux behavior.

## Target File Structure

`claude-cross-model-review` should have:

```text
SKILL.md
design-review.md
plan-review.md
execution.md
code-review.md
report.md
tmux-backend.md
lib/invoke-claude.sh
tests/test-invoke-claude-tmux.sh
```

`SKILL.md` becomes the orchestration entry point, not a container for large
inline phase templates. Phase-specific prompt templates and phase gates move to
the corresponding phase files, matching `cross-model-review`.

## Backend Model

### Tmux-Only Contract

The reviewer backend is an existing Claude Code pane selected by:

```text
--tmux-pane <target>
CLAUDE_REVIEW_TMUX_PANE=<target>
```

No hidden pane auto-detection is allowed. If no pane is provided, fail with
diagnostics listing available panes.

The pane must be in an auto-accept permission mode such as:

- `bypassPermissions`
- `dontAsk`

Plan mode, `acceptEdits`, and prompt-on-write modes are invalid for the full
lifecycle because the helper cannot answer interactive permission prompts.
`acceptEdits` may auto-accept file edits, but code review requires read-only
Bash commands such as `git diff origin/main --stat`; a pane that prompts for
Bash will hang until `lib/invoke-claude.sh` fails the round. The lifecycle
requires `bypassPermissions` or `dontAsk`.

### Accepted Read-Only Tradeoff

`cross-model-review` uses a reviewer backend that can be constrained by its
execution harness. A tmux-connected Claude Code pane does not provide harness
level read-only enforcement from Codex.

This spec explicitly accepts the tradeoff:

- The skill relies on prompt-level instructions telling Claude Code not to edit
  source/spec/helper/git files.
- `lib/invoke-claude.sh` performs after-the-fact side-effect detection.
- The only allowed git-visible side effect from a review round is the
  helper-designated output file and parent directories created for it.
- If any other git-visible change appears, the round fails. Review failure is
  not LGTM.

This is weaker than harness-level read-only because detection happens after the
reviewer turn, not before a write attempt. It is acceptable only because tmux is
the required backend difference, and because the helper fails closed on
unexpected side effects.

### Round Semantics

`cross-model-review` starts a new reviewer thread on Round 1 and resumes that
thread on Round N.

The tmux equivalent is:

- Round 1: send a full phase prompt to the same explicit Claude Code pane and
  require output in a fresh result file.
- Round N: send an incremental prompt to the same pane and require output in a
  new result file.

Continuity is maintained by:

- the Claude Code pane context when still available
- the issue tracker included in prompts
- explicit re-read instructions for changed files
- the newly designated output file for each round

Pane scrollback remains diagnostics only. The result file is the source of
truth.

## Role Mapping

`cross-model-review` assumes Claude orchestrates and Codex reviews.

`claude-cross-model-review` must invert the roles:

| Concern | cross-model-review | claude-cross-model-review |
|---|---|---|
| Orchestrator | Claude | Codex |
| External reviewer | Codex companion / fallback subagents | Claude Code in tmux |
| Convention file for reviewer | AGENTS.md for Codex backend | AGENTS.md for Claude Code pane |
| Artifact owner | Claude | Codex |
| Fix owner | Claude | Codex |
| Final decision owner | Claude | Codex |

Claude Code's output is evidence, not authority. Codex verifies every accepted
finding against the actual repository before changing files.

## Lifecycle

The skill must run the same autonomous lifecycle as `cross-model-review`:

```text
Design Review -> Plan Review -> Execution -> Code Review -> Report
```

The design-only path is also preserved:

```text
Design Review -> Report
```

Design-only mode is ON when either:

- the invocation explicitly says `--design-only`, `--spec-only`, `design only`,
  or `spec only`
- the user instruction says review only / do not implement / do not build /
  only review / `只评审` / `不实现` / `不建 repo` / `不写代码`

When design-only is ON, the skill must not create a plan, execute code, create a
PR, or run code review.

## Autonomous Flow

Copy the autonomous flow rule from `cross-model-review` with roles inverted:

- No asking the user whether to continue between phases.
- No asking whether to start execution after plan review.
- No asking whether to proceed to code review.
- Phase announcements and round progress are allowed.
- CEO decisions are made by Codex, not escalated to the user.

The one allowed pause remains the user-premise conflict escalation:

```text
If accepting a reviewer finding would overturn a decision the user explicitly
made, or invalidate the factual premise behind that decision, Codex must pause
and surface the conflict to the user before applying the fix.
```

This is not a confirmation prompt. It must name the explicit user decision, the
false premise, the evidence, and concrete choices.

## Phase Detection

Keep `cross-model-review` phase detection behavior, adapted to this skill:

1. Parse explicit phase:
   - `claude-cross-model-review design <path>`
   - `claude-cross-model-review plan <path>`
   - `claude-cross-model-review code`
2. If no explicit phase:
   - derive topic from current branch name
   - on `main` / `master`, fail with a concrete usage message
   - if an open PR exists on current branch, start at code review
   - if code changes exist versus `origin/main`, infer plan review or code
     review based on changed files
   - otherwise find matching plan/spec files under `docs/superpowers/`

The detected phase determines which phase file is read first. After a phase
completes, transitions are automatic.

## Prompt Variable Injection

Preserve placeholder injection from `cross-model-review`:

| Placeholder | Meaning |
|---|---|
| `<SPEC_FILE_PATH>` | resolved spec file or `N/A` |
| `<PLAN_FILE_PATH>` | resolved plan file or `N/A` |
| `<CONVENTION_FILE>` | `AGENTS.md (project root)` |
| `<PHASE>` | design, plan, or code |
| `<ROUND>` | review round number |

No raw `<PLACEHOLDER>` token may be sent to Claude Code. Prompt construction
must fail before dispatch if unresolved placeholders remain.

The review output path is not a phase-template placeholder. It is owned by
`lib/invoke-claude.sh`, which injects the helper-designated output file and
sentinel contract into the wrapper prompt at dispatch time. Phase prompts must
refer to "the helper-designated output file" without naming a path. If a future
orchestration layer pre-computes output paths, it must pass the exact same path
with `--output-file`; otherwise it must let the helper be the single owner of
output-file injection.

## Shared Review Loop

Each review phase uses the `cross-model-review` loop with the tmux backend:

1. Build a phase prompt from the phase file.
2. Dispatch Claude Code through `lib/invoke-claude.sh`.
3. Read the helper-designated output file.
4. Enforce sentinels:
   - `CLAUDE_REVIEW_RESULT_V1`
   - `CLAUDE_REVIEW_DONE`
5. For every issue at confidence `>= 70`:
   - VERIFY against current files.
   - EVALUATE whether it is correct for this project.
   - CLASSIFY as bug, missing requirement, intentional tradeoff, false
     positive, or user-premise conflict.
   - PREMISE-CHECK before applying a fix.
   - UPDATE the issue tracker.
   - ACCEPT or REJECT.
6. If accepted findings modify an artifact, re-dispatch Round 2+ before moving
   on.
7. Stop only on the same termination conditions as `cross-model-review`:
   - LGTM
   - all remaining issues rejected with no modifications
   - same issues repeated for two consecutive rounds
   - Round >= 4 and all open issues are verification requests below threshold
   - Round >= 5
8. For unresolved disagreements, make a CEO decision using the same structure as
   `cross-model-review`.
9. If a CEO verdict of ACCEPT or COMPROMISE modifies an artifact, run the same
   post-CEO verification as `cross-model-review`: Codex performs a lightweight
   single-pass self-check of the resulting diff, fixes any regression inline
   when it does not trip PREMISE-CHECK, and flags unverified CEO changes as
   `unreviewed` in the report.

Round 2+ processing must also preserve the fast-REJECT rule from
`cross-model-review`: if Claude Code re-raises an already rejected issue without
new concrete evidence, Codex rejects it immediately and does not let that stale
re-raise alone force a CEO decision. CEO fires only when the source termination
conditions are actually satisfied.

The issue tracker shape is unchanged:

```text
[phase, dimension, location, one-line summary, status, confidence]
```

Status values remain:

```text
open
accepted
rejected
ceo-accepted
ceo-rejected
ceo-compromised
user-override
```

## Phase Files

### `design-review.md`

Mirror `cross-model-review/design-review.md`.

Required adaptations:

- Reviewer is Claude Code.
- Phase prompts must be dispatched through `lib/invoke-claude.sh`, whose wrapper
  injects the helper-designated output file and sentinel contract.
- The phase reads `AGENTS.md` when present.
- ACCEPT action modifies the spec file.
- If accepted issues modify the spec, Round 2+ is mandatory.
- Next phase enforces design-only mode exactly like `cross-model-review`.
- If design-only mode is OFF and no implementation plan exists for the topic,
  Codex creates the plan before Plan Review. This mirrors the source
  `design-review.md` plan-creation step with role inversion: Codex uses the
  appropriate planning skill, skips the execution-handoff prompt, and skips the
  plan skill's internal review loop because `claude-cross-model-review` will run
  Plan Review through Claude Code.

### `plan-review.md`

Mirror `cross-model-review/plan-review.md`.

Required adaptations:

- Reviewer is Claude Code.
- Phase prompts must be dispatched through `lib/invoke-claude.sh`, whose wrapper
  injects the helper-designated output file and sentinel contract.
- ACCEPT action modifies the plan file.
- If accepted issues modify the plan, Round 2+ is mandatory.
- Next phase automatically proceeds to `execution.md`.

### `execution.md`

Mirror `cross-model-review/execution.md` with role inversion.

Codex executes the plan, not Claude Code. Claude Code remains reviewer only.

Execution must:

- re-read the reviewed plan
- record the base SHA
- choose an execution strategy automatically
- skip sub-skill confirmation prompts
- implement plan tasks
- run verification
- rebase on `origin/main`
- push or prepare diff as required for code review
- proceed automatically to `code-review.md`

Wallet/private-key operations remain skipped unless the user explicitly allows
them. The user-premise conflict escalation remains the only pause for review
premise conflicts.

### `code-review.md`

Mirror `cross-model-review/code-review.md`.

Required adaptations:

- Step 0 ensures a PR exists when possible, or reviews local diff if `gh` is not
  authenticated.
- Claude Code reviews the PR/diff through tmux.
- Prompt covers plan alignment, code logic, vulnerabilities, and data safety.
- Accepted fixes are implemented by Codex.
- Code fixes are committed one fix per commit.
- Round 2+ is mandatory after accepted fixes.

The final safety net is role-inverted:

- `cross-model-review` finishes Codex review with a Claude same-model safety
  net because Claude was the author.
- `claude-cross-model-review` finishes Claude review with a Codex same-model
  safety net because Codex is the author.

The Codex safety net must be a fresh local review of the final diff after the
Claude Code loop completes. It is not a tmux review and does not replace the
Claude Code external review. Any safety-net finding still goes through the full
Response Protocol, including PREMISE-CHECK.

After safety-net fixes, Codex performs a single-pass diff self-check and reports
whether modifications were self-checked.

### `report.md`

Mirror `cross-model-review/report.md` with backend and role names changed.

The report must include only phases that actually ran and must include:

- reviewer backend: `claude-code-tmux`
- tmux pane target
- spec path
- plan path
- PR URL or local diff mode
- started phase
- round counts and accepted/rejected counts
- CEO decisions
- CEO decision verification status: self-checked or unreviewed
- user-premise escalations
- Claude Code review result
- Codex safety-net result
- final status

## Helper Requirements

`lib/invoke-claude.sh` remains the backend primitive. It must continue to:

- require explicit pane selection
- wrap prompts with cwd, output path, write rules, and sentinels
- paste through tmux buffer
- wait for the sentinel-delimited output file
- validate output sentinels
- capture pane tail for timeout / permission diagnostics
- fail if unexpected git-visible changes appear
- never edit `.gitignore`, `.git/info/exclude`, git config, or other git files
  to hide review output

Any future orchestration layer should call this helper rather than reimplement
tmux paste/poll/side-effect logic.

## Migration Strategy

1. Add phase files by adapting `cross-model-review` with backend and role
   substitutions.
2. Rewrite `SKILL.md` as the orchestration entry point and remove large inline
   phase templates.
3. Preserve and update `tmux-backend.md` as the backend-specific reference.
4. Extend helper tests only where the new orchestration requirements expose
   helper behavior that is currently untested.
5. Add structure checks that prove the phase-file layout exists.
6. Run a Claude Code design review of this spec before writing the
   implementation plan.
7. Write and review the implementation plan before touching runtime behavior.

## Verification Requirements

The implementation plan must include concrete verification for:

- all required phase files exist
- `SKILL.md` references phase files instead of embedding full phase templates
- no Claude CLI backend references remain
- tmux backend still requires explicit pane selection
- helper tests still pass
- side-effect guard still rejects unexpected git-visible changes
- design-only mode is documented and enforceable
- Round 2+ is required after accepted modifications
- report format includes tmux pane and Codex safety-net result

## Risks

### Risk: Under-copying `cross-model-review`

If implementation only polishes the current helper workflow, it will fail the
user requirement. The required target is full lifecycle parity, not helper
ergonomics.

Mitigation: use `cross-model-review` files as the source templates and make
deviations explicit.

### Risk: Over-copying backend-specific Codex details

`cross-model-review` contains Codex companion and subagent fallback details that
do not apply to a tmux-only Claude Code backend.

Mitigation: copy lifecycle semantics, not Codex companion mechanics.

### Risk: Weak read-only enforcement

Tmux cannot prevent Claude Code from attempting writes at the harness layer.

Mitigation: make the accepted tradeoff explicit, keep prompt constraints, and
fail the round if the helper detects unexpected git-visible changes.

### Risk: Safety-net role confusion

The source skill uses Claude safety net because Claude authored the changes. In
this skill, Codex authors the changes.

Mitigation: invert the safety net. Claude Code remains the external reviewer;
Codex performs the final fresh local author-side safety review.

## Acceptance Criteria

This design is accepted when:

- Claude Code review finds no directional issue with the architecture parity
  target, or all accepted issues have been fixed and re-reviewed.
- The design explicitly limits intentional differences to tmux backend and
  role inversion.
- The design explicitly accepts the tmux read-only tradeoff.
- The next implementation plan can be written directly from this spec without
  re-litigating the target architecture.
