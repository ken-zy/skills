# Design: Add Claude-Primary Mode to tmux-cross-model-review

Date: 2026-06-28

## Problem

`tmux-cross-model-review` currently supports one role arrangement:

```text
Codex-primary: Codex is the terminal-session orchestrator and artifact owner.
Claude Code is an external reviewer reached through an explicit tmux reviewer
pane.
```

The user wants an additional mode with the roles reversed:

```text
Claude-primary: Claude Code is the terminal-session orchestrator and artifact
owner. Codex is the external reviewer and safety net.
```

This is not just "let Claude edit files through tmux." If Codex keeps sending
driver prompts to Claude Code, polling result files, counting rounds, advancing
phases, and owning the issue tracker, then Codex remains the real orchestrator
even if Claude Code writes the files.

The design must therefore separate two concepts:

- **who edits files**
- **who owns the lifecycle control loop**

True Claude-primary mode means Claude Code owns both.

## Goal

Add a second role mode without changing the existing default behavior.

```text
codex-primary   # default, current behavior
claude-primary  # new mode, Claude Code native session owns the lifecycle
```

Codex-primary remains the default. Claude-primary is explicit.

Both modes must use the same cross-model interaction shape:

```text
primary session -> prompt file -> explicit tmux reviewer pane -> review result Markdown
```

The primary and secondary models must not be run as two roles inside one
conversation or one local review command.

## Non-Goals

- Do not remove or weaken Codex-primary behavior.
- Do not make Claude-primary the default.
- Do not add hidden pane auto-detection.
- Do not build a write-enabled Claude driver controlled by Codex.
- Do not run both models inside one conversation/dialog and call that
  cross-model review.
- Do not let either mode bypass the user-premise conflict escalation rule.
- Do not require GitHub PRs; local diff review remains valid.
- Do not use non-tmux reviewer transports such as `codex review` for
  Claude-primary mode.

## Shared Lifecycle

Both modes preserve the same conceptual lifecycle:

```text
Design Review -> Plan Review -> Execution -> Code Review -> Report
Design-only: Design Review -> Report
```

Both modes preserve:

- design-only/spec-only termination
- phase auto-transition
- Round 2+ after accepted modifications
- issue tracker
- confidence threshold `>= 70`
- VERIFY -> EVALUATE -> CLASSIFY -> PREMISE-CHECK -> UPDATE -> ACCEPT/REJECT
- CEO Decision after repeated disagreement or round limit
- user-premise conflict escalation as the only allowed user pause
- `AGENTS.md` resolution rule:
  - if project-root `AGENTS.md` exists, the active reviewer must read it
  - if absent, inject and record `no convention file available`
- temporary prompt files outside the repository
- Markdown review result files under a dated `docs/reviews/.../YYYYMMDD/`
  location

## Role Matrix

| Concern | `codex-primary` | `claude-primary` |
|---|---|---|
| Terminal-session orchestrator | Codex | Claude Code |
| Artifact owner | Codex | Claude Code |
| Execution owner | Codex | Claude Code |
| Fix owner | Codex | Claude Code |
| Issue tracker owner | Codex | Claude Code |
| Phase transition owner | Codex | Claude Code |
| External reviewer | Claude Code | Codex |
| Final decision owner | Codex | Claude Code |
| Reviewer bridge direction | Codex -> Claude Code over tmux | Claude Code -> Codex over tmux |

The important invariant is:

```text
The primary model owns the lifecycle loop. The secondary model only reviews.
```

## Mode Selection

Mode selection is explicit:

```text
--mode codex-primary
--mode claude-primary
```

Aliases may be accepted:

```text
--codex-primary
--claude-primary
```

If no mode is passed, use `codex-primary`.

The selected mode is resolved once at startup and included in every phase prompt
and final report.

## Codex-Primary Mode

Codex-primary mode is the current behavior.

Codex owns:

- phase detection
- prompt construction
- issue tracker
- VERIFY/EVALUATE/CLASSIFY/PREMISE-CHECK
- artifact edits
- execution
- final report

Claude Code is reached through the existing review-only helper:

```text
lib/invoke-claude.sh
```

The interaction shape is:

```text
Codex primary -> prompt file -> Claude Code tmux reviewer pane -> Claude review result Markdown
```

Allowed Claude Code side effects remain:

- the designated Claude review result Markdown file
- parent directories created only to hold that result file

Any other git-visible change fails the review round. Review failure is not
LGTM.

No behavior change is required for Codex-primary mode.

## Claude-Primary Mode

Claude-primary mode runs from a native Claude Code session.

Claude Code owns:

- phase detection
- prompt construction
- issue tracker
- VERIFY/EVALUATE/CLASSIFY/PREMISE-CHECK
- artifact edits
- execution
- final report

Codex is reached only as a reviewer. Codex does not drive Claude Code, does not
advance phases, and does not own the issue tracker.

### Entry Point

Claude-primary mode requires a Claude-facing entrypoint in this repository, for
example:

```text
claude-primary.md
```

That entrypoint describes the same lifecycle and phase files, but from Claude
Code's perspective:

```text
You are Claude Code. You are the primary driver. Use Codex only as the external
reviewer. You own edits, verification, issue tracking, phase transitions, and
the final report.
```

If Codex receives a request to run `--mode claude-primary`, Codex must not
simulate Claude-primary by remotely driving a Claude pane. It may only produce a
handoff instruction telling the user to run the Claude-facing entrypoint from a
Claude Code session.

### Reviewer Bridge

Claude-primary mode needs a Codex tmux reviewer bridge, the mirror image of the
current Claude tmux review helper.

Conceptually:

```text
Codex-primary:
  Codex orchestrates -> calls Claude tmux review helper -> Claude writes review result

Claude-primary:
  Claude orchestrates -> calls Codex tmux review helper -> Codex writes review result
```

The supported transport for this bridge is an explicit tmux pane running Codex.
The target pane must be provided explicitly:

```text
--codex-tmux-pane <target>
CODEX_REVIEW_TMUX_PANE=<target>
```

No pane auto-detection is allowed. If no Codex reviewer pane is provided,
Claude-primary mode must fail with available-pane diagnostics.

If the provided pane is not reachable or does not produce the required result
file, Claude-primary mode must fail with a diagnostic such as:

```text
Claude-primary requires an explicit Codex tmux reviewer pane, but the configured
pane did not produce a valid review result.
```

It must not silently fall back to same-model review, local-only review, or
non-tmux Codex review and call that cross-model review.

Wrap the tmux interaction in a small helper so Claude Code does not have to
re-create prompt delivery, output-file polling, sentinel validation, and
side-effect checking in every phase:

```text
lib/invoke-codex-tmux.sh
```

The helper is review-only. It loads the wrapped review prompt into a tmux
buffer, pastes it into the Codex reviewer pane, waits for Codex to write the
designated result Markdown file, and verifies no forbidden repository writes
occurred during the review.

### Codex Review Result Contract

Codex reviewer rounds write Markdown result files under:

```text
docs/reviews/codex/YYYYMMDD/*.md
```

Each Codex review result contains:

```markdown
CODEX_REVIEW_RESULT_V1

# Codex Review

## Result

<ISSUE entries or LGTM>

CODEX_REVIEW_DONE
```

Claude Code reads the result file. Codex pane scrollback is diagnostics only.

### Codex Reviewer Pane Requirements

The Codex reviewer pane must already be running a Codex session in a mode that
can read repository files and write the designated result file without
interactive permission prompts. The helper cannot answer prompts inside the
Codex pane.

The required pane state is an interactive Codex CLI session started with the
reviewer equivalent of:

```bash
codex --cd /path/to/repo \
  --sandbox workspace-write \
  --ask-for-approval never \
  --no-alt-screen
```

The same settings may come from a Codex profile, but the effective behavior must
match those flags:

- `--ask-for-approval never` is required because the helper cannot answer
  command or write approval prompts inside the reviewer pane.
- `--sandbox workspace-write` is required so Codex can read the repository and
  write the designated review result file, while ordinary filesystem writes
  remain sandboxed to the workspace.
- `--no-alt-screen` is required for usable diagnostics when the helper captures
  pane scrollback after a timeout or permission failure.

Invalid pane states:

- `--ask-for-approval untrusted`
- `--ask-for-approval on-request`
- `--ask-for-approval on-failure`
- any profile or runtime mode that can pause for interactive approval

`--dangerously-bypass-approvals-and-sandbox` is not the default reviewer mode.
It may only be used if the pane is externally sandboxed and the user explicitly
opts into that risk.

Before the first real Claude-primary review round, `lib/invoke-codex-tmux.sh`
must run a small preflight against the configured pane: send a minimal prompt
that writes the required Codex review sentinels to a designated preflight output
file under `docs/reviews/codex/YYYYMMDD/`, then validate the file and run the
same side-effect guard used for review rounds. If preflight fails, Claude-primary
mode is unavailable and must fail loudly before plan or code execution.

### Codex Reviewer Side-Effect Guard

The Codex reviewer bridge is review-only.

Allowed Codex reviewer side effects:

- the designated Codex review result Markdown file
- parent directories created only to hold that result file

Forbidden side effects:

- edits to source/spec/plan/code files
- edits to git metadata or ignore files
- edits to real secret files such as `.env`, `.env.production`, or files
  containing live credentials
- destructive operations

If Codex reviewer side effects exceed this boundary, the review round fails.
Review failure is not LGTM.

### Claude Writes Natively

Claude-primary mode does not need a write-enabled tmux driver helper.

Claude Code already has native abilities to:

- edit specs
- edit plans
- edit source files
- run commands
- run tests
- commit when required by the phase

Those writes are normal primary-driver actions, not reviewer side effects. They
are reviewed by Codex through the Codex tmux reviewer bridge.

## Phase Ownership

In Claude-primary mode:

- Phase 1 Design Review:
  - Claude Code creates or updates the spec.
  - Codex reviews the spec for directional issues.
  - Claude Code processes accepted Codex findings and modifies the spec.
- Phase 2 Plan Review:
  - Claude Code creates or updates the implementation plan.
  - Codex reviews plan alignment and execution completeness.
  - Claude Code processes accepted Codex findings and modifies the plan.
- Phase 3 Execution:
  - Claude Code executes the reviewed plan.
  - Claude Code runs verification commands.
  - Codex reviews the resulting diff and verification evidence.
- Phase 4 Code Review:
  - Codex performs the external code review.
  - Claude Code applies accepted fixes.
  - Round 2+ is mandatory after accepted fixes.
- Phase 5 Report:
  - Claude Code writes the report.
  - The report includes Codex review rounds and any unresolved items.

## Response Protocol

The response protocol remains symmetric:

```text
VERIFY -> EVALUATE -> CLASSIFY -> PREMISE-CHECK -> UPDATE -> ACCEPT/REJECT
```

In Claude-primary mode, Claude Code runs the protocol because Claude Code owns
the artifact. Codex findings are evidence, not authority.

In Codex-primary mode, Codex runs the protocol because Codex owns the artifact.
Claude Code findings are evidence, not authority.

## Conflict Escalation

The ONE Exception keeps the same meaning in both modes.

If the primary model is about to accept a reviewer finding and applying it would
overturn an explicit user decision or invalidate that decision's factual premise,
the primary model pauses and escalates to the user before applying the fix.

The escalation must state:

- the explicit user decision
- the factual premise now believed to be false
- the evidence
- concrete options

After the user chooses, the primary model records `user-override` in the issue
tracker and resumes the pipeline.

## Prompt Changes

Every phase prompt receives a role banner:

```text
ROLE MODE: codex-primary
Codex is the primary driver and artifact owner. Claude Code is reviewer only.
Codex owns the lifecycle loop.
```

or:

```text
ROLE MODE: claude-primary
Claude Code is the primary driver and artifact owner. Codex is reviewer only.
Claude Code owns the lifecycle loop.
```

Prompt wording must avoid ambiguous labels like "author" or "reviewer" without
identifying the active model for the selected mode.

## Report Changes

The final report includes:

```markdown
| Role mode | codex-primary / claude-primary |
| Primary driver | Codex / Claude Code |
| External reviewer | Claude Code / Codex |
| Primary result owner | Codex / Claude Code |
```

For Claude-primary mode, report sections distinguish:

- Claude driver actions
- Codex review rounds
- Claude-applied fixes
- user-premise escalations
- unresolved review failures

## Testing Strategy

Add static structure tests for:

- `codex-primary` remains the default
- `claude-primary` is documented as Claude-native, not Codex-driven
- `lib/invoke-claude.sh` remains review-only
- no runtime doc introduces `lib/invoke-claude-driver.sh`
- no runtime doc uses non-tmux Codex transports such as `codex review` for the
  Claude-primary reviewer bridge
- the Codex tmux reviewer helper is documented separately from Claude writes
- the Codex reviewer pane state requires `--ask-for-approval never`,
  `--sandbox workspace-write`, and `--no-alt-screen`, or an equivalent profile
- Codex review result sentinels are documented
- report output includes role mode fields

Add bridge tests for the Codex tmux helper:

- preflights the Codex reviewer pane before the first real review round
- requires explicit Codex tmux pane
- requires explicit review output file
- rejects missing prompt file
- writes/reads `CODEX_REVIEW_RESULT_V1` and `CODEX_REVIEW_DONE`
- rejects source/spec/helper/git mutations by the reviewer
- returns a clear diagnostic when the Codex pane is missing or waiting on a
  permission prompt

Existing `lib/invoke-claude.sh` tests must continue proving that Codex-primary
Claude review rounds are read-only.

## Migration Plan

1. Add mode-selection documentation and static tests.
2. Add the Claude-facing entrypoint for Claude-primary mode.
3. Add `lib/invoke-codex-tmux.sh` as the Codex reviewer-pane helper.
4. Add Codex reviewer-pane preflight before any Claude-primary plan or code
   execution.
5. Update `SKILL.md` to keep Codex-primary as default and to hand off, not
   simulate, Claude-primary requests.
6. Update phase files to use explicit role banners and role-neutral mechanics.
7. Update `report.md` with role mode fields.
8. Run existing structure/helper tests plus Codex reviewer bridge tests.

## Open Questions

None. The design pins the concrete Claude->Codex reviewer transport to an
explicit Codex tmux reviewer pane running with non-interactive approval behavior
and requires a preflight before Claude-primary can proceed.
